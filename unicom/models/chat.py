from __future__ import annotations
from typing import TYPE_CHECKING
from django.db import models
from .constants import channels
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

if TYPE_CHECKING:
    from unicom.models import Message


class Chat(models.Model):
    id = models.CharField(max_length=500, primary_key=True)
    channel = models.ForeignKey('unicom.Channel', on_delete=models.CASCADE)
    platform = models.CharField(max_length=100, choices=channels)
    is_private = models.BooleanField(default=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    # accounts = models.ManyToManyField('unicom.Account', related_name="chats")

    def send_message(self, msg_dict: dict, user:User=None) -> Message:
        """
        Send a message to this chat using the channel's platform.
        The msg_dict must include at least the text or media to send.
        
        For email channels, this will find the last incoming message and reply to it,
        ensuring proper email threading and recipient handling.
        For other platforms (Telegram, WhatsApp), it sends the message directly to the chat.
        """
        if not self.channel.active:
            raise ValueError("Channel must be active to send messages.")
        
        try:
            if self.platform == 'Email':
                # For email, find the last incoming message and reply to it
                last_incoming = self.messages.filter(
                    is_outgoing=False
                ).order_by('-timestamp').first()
                
                if not last_incoming:
                    raise ValidationError("No incoming messages found in this email chat to reply to")
                
                # Use Message.reply_with which handles all email threading and recipient logic
                return last_incoming.reply_with(msg_dict)
            else:
                # For other platforms, just send to the chat directly
                from unicom.services.crossplatform.send_message import send_message
                return send_message(self.channel, {**msg_dict, "chat_id": self.id}, user)
                
        except Exception as e:
            raise ValueError(f"Failed to send message: {str(e)}")

    def __str__(self) -> str:
        return f"{self.platform}:{self.id} ({self.name})"