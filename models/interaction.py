import uuid
from django.db import models


class Interaction(models.Model):
    """One persisted, resumable user interaction per tool invocation."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tool_call = models.OneToOneField('unicom.ToolCall', on_delete=models.CASCADE, related_name='interaction')
    account = models.ForeignKey('unicom.Account', on_delete=models.CASCADE)
    message = models.OneToOneField('unicom.Message', on_delete=models.CASCADE, related_name='interaction')
    handler = models.CharField(max_length=255)
    state = models.JSONField(default=dict)
    presentation = models.JSONField(default=dict)
    component = models.JSONField(default=dict)
    buttons = models.JSONField(default=list)
    text = models.TextField()
    status = models.CharField(max_length=20, default='awaiting_input', choices=[
        ('awaiting_input', 'Awaiting input'), ('completed', 'Completed'),
        ('cancelled', 'Cancelled'), ('expired', 'Expired'), ('error', 'Error'),
    ])
    revision = models.PositiveIntegerField(default=0)
    result = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
