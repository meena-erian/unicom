from django.db import models
from django.contrib.auth.models import User
from unicom.models.constants import channels
from django.contrib.postgres.fields import ArrayField
from django.core.validators import validate_email
from fa2svg.converter import revert_to_original_fa


class Message(models.Model):
    TYPE_CHOICES = [
        ('text', 'Text'),
        ('html', 'HTML'),
        ('image', 'Image'),
        ('audio', 'Audio'),
    ]
    id = models.CharField(max_length=500, primary_key=True)
    platform = models.CharField(max_length=100, choices=channels)
    sender = models.ForeignKey('unicom.Account', on_delete=models.RESTRICT)
    user = models.ForeignKey(User, on_delete=models.RESTRICT, null=True, blank=True)
    chat = models.ForeignKey('unicom.Chat', on_delete=models.CASCADE, related_name='messages')
    is_bot = models.BooleanField(default=False)
    sender_name = models.CharField(max_length=100)
    subject = models.CharField(max_length=512, blank=True, null=True, help_text="Subject of the message (only for email messages)")
    text = models.TextField()
    html = models.TextField(
        blank=True, null=True,
        help_text="Full HTML body (only for email messages)"
    )
    to  = ArrayField(
        base_field=models.EmailField(validators=[validate_email]),
        blank=True,
        default=list,
        help_text="List of To: addresses",
    )
    cc  = ArrayField(
        base_field=models.EmailField(validators=[validate_email]),
        blank=True,
        default=list,
        help_text="List of Cc: addresses",
    )
    bcc = ArrayField(
        base_field=models.EmailField(validators=[validate_email]),
        blank=True,
        default=list,
        help_text="List of Bcc: addresses",
    )
    media = models.FileField(upload_to='media/', blank=True, null=True)
    reply_to_message = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    timestamp = models.DateTimeField()
    time_sent = models.DateTimeField(null=True, blank=True)
    time_delivered = models.DateTimeField(null=True, blank=True)
    time_seen = models.DateTimeField(null=True, blank=True)
    sent = models.BooleanField(default=False)
    delivered = models.BooleanField(default=False)
    seen = models.BooleanField(default=False)
    raw = models.JSONField()
    media_type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='text'
    )
    # Add any additional fields as needed for specific platforms

    @property
    def original_content(self):
        return revert_to_original_fa(self.html) if self.platform == 'Email' else self.text

    class Meta:
        ordering = ['-timestamp']

    def __str__(self) -> str:
        return f"{self.platform}:{self.chat_id}:{self.id}->{self.sender_id}({self.sender_name}): {self.text}"
