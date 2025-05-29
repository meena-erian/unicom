from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
import uuid


class Request(models.Model):
    """
    Model for incoming message tasks with categorization and metadata.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IDENTIFYING', 'Identifying'),
        ('CATEGORIZING', 'Categorizing'),
        ('QUEUED', 'Queued'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey('unicom.Message', on_delete=models.CASCADE)
    account = models.ForeignKey('unicom.Account', on_delete=models.CASCADE)
    channel = models.ForeignKey(
        'unicom.Channel',
        on_delete=models.CASCADE,
        help_text="Channel where this request originated"
    )
    member = models.ForeignKey(
        'unicom.Member',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=True
    )
    
    # Contact information that might help identify the member
    email = models.EmailField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Email address extracted from the Account"
    )
    phone = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Phone number extracted from the Account"
    )
    
    category = models.ForeignKey(
        'unicom.RequestCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
        help_text="Current category of the request"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    error = models.TextField(
        null=True,
        blank=True,
        help_text="Detailed error message when request fails"
    )
    metadata = models.JSONField(default=dict)
    
    # Timestamps for request lifecycle
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    pending_at = models.DateTimeField(auto_now_add=True)
    identifying_at = models.DateTimeField(null=True, blank=True)
    categorizing_at = models.DateTimeField(null=True, blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    processing_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            # Compound index for contact fields
            models.Index(fields=['email', 'phone'], name='request_contact_idx'),
            # Index for status with timestamps for filtering requests in specific states
            models.Index(fields=['status', 'created_at'], name='request_status_created_idx'),
            models.Index(fields=['status', 'completed_at'], name='request_status_completed_idx'),
            # Index for category lookups with status
            models.Index(fields=['category', 'status'], name='request_category_status_idx'),
            # Index for channel-based lookups
            models.Index(fields=['channel', 'status'], name='request_channel_status_idx'),
        ]

    def __str__(self):
        return f"Request {self.id} - {self.status}"

    def save(self, *args, **kwargs):
        # Set channel from message if not set
        if not self.channel and self.message:
            self.channel = self.message.channel

        # Update status timestamps
        if not self.pk:  # New instance
            self.pending_at = timezone.now()
        else:
            try:
                old_instance = type(self).objects.get(pk=self.pk)
                if old_instance.status != self.status:
                    timestamp_field = f"{self.status.lower()}_at"
                    if hasattr(self, timestamp_field):
                        setattr(self, timestamp_field, timezone.now())
            except type(self).DoesNotExist:
                # This is a new instance but with a predefined pk
                self.pending_at = timezone.now()
        
        super().save(*args, **kwargs)

    def get_available_categories(self, parent=None):
        """
        Get categories available to this request at the specified level,
        taking into account permissions and channel restrictions.
        """
        from .request_category import RequestCategory

        # Base query for active categories at this level
        categories = RequestCategory.objects.filter(
            parent=parent,
            is_active=True
        )

        # Filter by channel if category specifies allowed channels
        channel_categories = categories.filter(
            Q(allowed_channels=self.channel) | Q(allowed_channels__isnull=True)
        )

        # Filter by permissions
        if self.member:
            # Get categories the member has access to through:
            # 1. Public categories
            # 2. Direct member authorization (allowed_categories M2M from Member)
            # 3. Direct member authorization (authorized_members M2M from Category)
            # 4. Group membership
            member_categories = channel_categories.filter(
                Q(is_public=True) |  # Public access
                Q(members_with_access=self.member) |  # Via Member.allowed_categories
                Q(authorized_members=self.member) |  # Via Category.authorized_members
                Q(authorized_groups__members=self.member)  # Group-based access
            )
            return member_categories.distinct().order_by('sequence')
        else:
            # Only public categories for non-members
            return channel_categories.filter(is_public=True).order_by('sequence')

    def identify_member(self):
        """
        Identify and link member if not already set.
        Tries multiple methods:
        1. Check if member is already set
        2. Check if account has a member
        3. Look for member with matching email
        4. Look for member with matching phone
        """
        try:
            # Skip if member is already set
            if self.member:
                return True

            # Skip if account doesn't exist
            if not self.account:
                self.error = "No account associated with request"
                self.save(update_fields=['error'])
                return False

            # If account already has a member, use that
            if self.account.member:
                self.member = self.account.member
                self.save()
                return True

            # Try to find member by contact information
            from .member import Member
            matching_member = None

            # Build query for contact matching
            contact_query = Q()
            if self.email:
                contact_query |= Q(email=self.email)
            if self.phone:
                contact_query |= Q(phone=self.phone)

            if contact_query:
                try:
                    matching_member = Member.objects.filter(contact_query).first()
                except Member.MultipleObjectsReturned:
                    self.error = "Multiple members found with matching contact info"
                    self.metadata['member_identification'] = {
                        'error': self.error,
                        'email': self.email,
                        'phone': self.phone
                    }
                    self.save()
                    return False

            if matching_member:
                self.member = matching_member
                self.metadata['member_identification'] = {
                    'method': 'contact_match',
                    'matched_by': 'email' if self.email and self.email == matching_member.email else 'phone'
                }
                self.save()
                
                # Also update the account if found by contact info
                if self.account and not self.account.member:
                    self.account.member = matching_member
                    self.account.save()
                
                return True

            # No member found but this is not an error condition
            self.metadata['member_identification'] = {
                'result': 'no_match',
                'email': self.email,
                'phone': self.phone
            }
            self.save()
            return False

        except Exception as e:
            self.error = f"Error during member identification: {str(e)}"
            self.save(update_fields=['error'])
            return False

    def categorize(self):
        """
        Attempt to categorize the request by running through category functions.
        Updates status based on results.
        """
        self.status = 'CATEGORIZING'
        self.error = None  # Clear any previous errors
        self.save()

        try:
            # Start categorization from top level (no parent)
            if self._try_categorize_with_children(None):
                return True
            
            # If no category matched, that's fine - treat null as a valid state
            self.category = None
            self.status = 'QUEUED'
            self.save()
            return True
            
        except Exception as e:
            self.status = 'FAILED'
            self.error = f"Error during categorization: {str(e)}"
            self.save()
            return False

    def _try_categorize_with_children(self, parent_category=None):
        """
        Recursive helper for categorization.
        Returns True if a matching category was found and set.
        """
        try:
            # Get permitted categories at current level
            categories = self.get_available_categories(parent_category)
            
            # If exactly one category is available, use it without processing
            if categories.count() == 1:
                category = categories.first()
                self.category = category
                self.status = 'QUEUED' if not category.subcategories.filter(is_active=True).exists() else 'CATEGORIZING'
                self.save()
                return True

            # Otherwise process each category
            for category in categories:
                try:
                    # Run category's processing function
                    result = category.process_request(self)
                    
                    # If category matched (returned True in metadata)
                    if result.get('category_match', False):
                        self.category = category
                        self.metadata.update(result)
                        self.save()

                        # Check if category has subcategories
                        if category.subcategories.filter(is_active=True).exists():
                            # Continue categorizing with subcategories
                            return self._try_categorize_with_children(category)
                        else:
                            # No subcategories, mark as queued
                            self.status = 'QUEUED'
                            self.save()
                            return True
                except Exception as e:
                    # Log error in metadata but continue with next category
                    self.metadata['categorization_errors'] = self.metadata.get('categorization_errors', [])
                    self.metadata['categorization_errors'].append({
                        'category': category.name,
                        'error': str(e)
                    })
                    self.save()
                    continue

            # No matching category found at this level - that's okay
            return False

        except Exception as e:
            self.error = f"Error during category processing: {str(e)}"
            self.save(update_fields=['error'])
            return False

    def process_category(self):
        """
        Process the request's category and update metadata.
        """
        # No category is a valid state - just mark as completed
        if not self.category:
            self.status = 'COMPLETED'
            self.save()
            return
        
        self.status = 'PROCESSING'
        self.error = None  # Clear any previous errors
        self.save()

        try:
            self.metadata = self.category.process_request(self)
            self.save()
            
            self.status = 'COMPLETED'
            self.save()
        except Exception as e:
            self.status = 'FAILED'
            self.error = f"Error during category processing: {str(e)}"
            self.save()
            raise 