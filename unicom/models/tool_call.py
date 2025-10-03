from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid


class ToolCall(models.Model):
    """Task queue model for tracking tool calls awaiting responses"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('ERROR', 'Error'),
        ('INTERRUPTED', 'Interrupted'),
        ('ACTIVE', 'Active'),  # For periodic/ongoing tool calls
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    call_id = models.CharField(max_length=100, unique=True, db_index=True)
    tool_name = models.CharField(max_length=100, db_index=True)
    arguments = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    error = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if processing fails"
    )
    
    # Reference to the request that created this tool call
    request = models.ForeignKey('unicom.Request', on_delete=models.CASCADE, related_name='tool_calls')
    
    # Reference to the tool call message (for proper reply chain)
    tool_call_message = models.ForeignKey(
        'unicom.Message', 
        on_delete=models.CASCADE, 
        related_name='tool_call_record',
        help_text="The tool_call message that this ToolCall object represents"
    )
    
    # Reference to the initial user message that triggered this tool call
    initial_user_message = models.ForeignKey(
        'unicom.Message',
        on_delete=models.CASCADE,
        related_name='triggered_tool_calls',
        help_text="The original user message that this tool call is responding to"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['tool_name', 'status']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tool_name}:{self.call_id} ({self.status})"
    
    def clean(self):
        """Validate that tool_call_message is actually a tool call message"""
        if self.tool_call_message and self.tool_call_message.media_type != 'tool_call':
            raise ValidationError("tool_call_message must have media_type='tool_call'")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def start_processing(self):
        """Mark tool call as in progress"""
        self.status = 'IN_PROGRESS'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_active(self):
        """Mark tool call as active for periodic responses"""
        self.status = 'ACTIVE'
        self.save(update_fields=['status'])
    
    def mark_error(self, error_message=None):
        """Mark tool call as failed"""
        self.status = 'ERROR'
        self.completed_at = timezone.now()
        if error_message:
            self.error = error_message
        self.save(update_fields=['status', 'completed_at', 'error'])
    
    def interrupt(self):
        """Mark tool call as interrupted"""
        self.status = 'INTERRUPTED'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def respond(self, result):
        """
        Submit response to this tool call.
        
        Args:
            result: The result from the tool execution (any JSON-serializable object)
        
        Returns:
            Tuple of (tool_response_message, child_request_or_None)
            
        Behavior:
        - For PENDING status: Marks as COMPLETED, creates child request if final
        - For IN_PROGRESS status: Marks as COMPLETED, creates child request if final
        - For ACTIVE status: Logs response but keeps ACTIVE, no child request
        - For other statuses: Raises ValueError
        """
        # Validate current status
        if self.status not in ['PENDING', 'IN_PROGRESS', 'ACTIVE']:
            raise ValueError(f"Cannot respond to tool call with status: {self.status}")
        
        # Create tool response message for LLM context - reply to the tool call message
        tool_response_msg = self.tool_call_message.log_tool_interaction(
            tool_response={"call_id": self.call_id, "result": result}
        )
        
        # Handle response based on current status
        with transaction.atomic():
            # Only mark as completed if not ACTIVE (ACTIVE stays active for reusable buttons)
            if self.status != 'ACTIVE':
                self.status = 'COMPLETED'
                self.completed_at = timezone.now()
                self.save(update_fields=['status', 'completed_at'])
            
            # Check if this is the final response (all PENDING tool calls now COMPLETED)
            pending_calls = self.request.tool_calls.filter(status='PENDING').count()
            
            if pending_calls == 0:
                # This is the final response - create child request
                # Use initial_request to get the root request for field propagation
                initial_req = self.request.initial_request or self.request
                
                child_request = self.request.__class__.objects.create(
                    message=tool_response_msg,
                    # Propagate fields from initial request
                    account=initial_req.account,
                    channel=initial_req.channel,
                    member=initial_req.member,
                    email=initial_req.email,
                    phone=initial_req.phone,
                    category=initial_req.category,  # Propagate category from initial request
                    # Set hierarchy fields
                    parent_request=self.request,
                    initial_request=initial_req,
                    display_text=f"Tool response: {str(result)[:100]}...",
                    status='PENDING',
                    metadata={
                        'created_from': 'tool_response',
                        'parent_request_id': str(self.request.id),
                        'initial_request_id': str(initial_req.id),
                        'final_tool_call_id': self.call_id,
                        'tool_name': self.tool_name,
                    }
                )
                
                # Process child request through normal pipeline
                child_request.identify_member()
                child_request.categorize()
                
                return tool_response_msg, child_request
        
        return tool_response_msg, None