from __future__ import annotations
from typing import TYPE_CHECKING
from django.db import models
from django.contrib.auth.models import User
from unicom.models.constants import channels
from django.contrib.postgres.fields import ArrayField
from django.core.validators import validate_email
from fa2svg.converter import revert_to_original_fa
import uuid
import re
from bs4 import BeautifulSoup
import base64
from .fields import DedupFileField, only_delete_file_if_unused

if TYPE_CHECKING:
    from unicom.models import Channel


class Message(models.Model):
    TYPE_CHOICES = [
        ('text', 'Text'),
        ('html', 'HTML'),
        ('image', 'Image'),
        ('audio', 'Audio'),
    ]
    id = models.CharField(max_length=500, primary_key=True)
    channel = models.ForeignKey('unicom.Channel', on_delete=models.CASCADE)
    platform = models.CharField(max_length=100, choices=channels)
    sender = models.ForeignKey('unicom.Account', on_delete=models.RESTRICT)
    user = models.ForeignKey(User, on_delete=models.RESTRICT, null=True, blank=True)
    chat = models.ForeignKey('unicom.Chat', on_delete=models.CASCADE, related_name='messages')
    is_outgoing = models.BooleanField(null=True, default=None, help_text="True for outgoing messages, False for incoming, None for internal")
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
    # Email tracking fields
    tracking_id = models.UUIDField(default=uuid.uuid4, null=True, blank=True, help_text="Unique ID for tracking email opens and clicks")
    time_opened = models.DateTimeField(null=True, blank=True, help_text="When the email was first opened")
    opened = models.BooleanField(default=False, help_text="Whether the email has been opened")
    time_link_clicked = models.DateTimeField(null=True, blank=True, help_text="When a link in the email was first clicked")
    link_clicked = models.BooleanField(default=False, help_text="Whether any link in the email has been clicked")
    clicked_links = ArrayField(
        base_field=models.URLField(),
        blank=True,
        null=True,
        default=list,
        help_text="List of links that have been clicked"
    )

    def reply_with(self, msg_dict:dict) -> Message:
        """
        Reply to this message with a dictionary containing the response.
        The dictionary can contain 'text', 'html', 'file_path', etc.
        """
        from unicom.services.crossplatform.reply_to_message import reply_to_message
        return reply_to_message(self.channel, self, msg_dict)

    @property
    def original_content(self):
        return revert_to_original_fa(self.html) if self.platform == 'Email' else self.text

    @property
    def html_with_base64_images(self):
        """
        Returns the HTML content with all inline image shortlinks replaced by their original base64 data, if available.
        """
        if not self.html:
            return self.html
        soup = BeautifulSoup(self.html, 'html.parser')
        # Map shortlink src to base64 for all inline images
        images = {img.get_short_id(): img for img in getattr(self, 'inline_images', [])}
        for img_tag in soup.find_all('img'):
            src = img_tag.get('src', '')
            # Extract short id from src (e.g., /i/abc123 or full URL)
            m = re.search(r'/i/([A-Za-z0-9]+)', src)
            if m:
                short_id = m.group(1)
                image_obj = images.get(short_id)
                if image_obj:
                    # Read file and encode as base64
                    data = image_obj.file.read()
                    image_obj.file.seek(0)
                    mime = 'image/png'  # Default
                    if hasattr(image_obj.file, 'file') and hasattr(image_obj.file.file, 'content_type'):
                        mime = image_obj.file.file.content_type
                    elif image_obj.file.name:
                        import mimetypes
                        mime = mimetypes.guess_type(image_obj.file.name)[0] or 'image/png'
                    b64 = base64.b64encode(data).decode('ascii')
                    img_tag['src'] = f'data:{mime};base64,{b64}'
        return str(soup)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self) -> str:
        return f"{self.platform}:{self.chat.name}->{self.sender_name}: {self.text}"


class EmailInlineImage(models.Model):
    file = DedupFileField(upload_to='email_inline_images/', hash_field='hash')
    email_message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='inline_images', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    content_id = models.CharField(max_length=255, blank=True, null=True, help_text='Content-ID for cid: references in HTML')
    hash = models.CharField(max_length=64, blank=True, null=True, db_index=True, help_text='SHA256 hash of file for deduplication')

    def delete(self, *args, **kwargs):
        only_delete_file_if_unused(self, 'file', 'hash')
        super().delete(*args, **kwargs)

    def get_short_id(self):
        # Use base62 encoding of PK for short URLs
        import string
        chars = string.digits + string.ascii_letters
        n = self.pk
        s = ''
        if n == 0:
            return chars[0]
        while n > 0:
            n, r = divmod(n, 62)
            s = chars[r] + s
        return s
