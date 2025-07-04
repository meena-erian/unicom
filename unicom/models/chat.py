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
    is_archived = models.BooleanField(default=False, help_text="Archived chats are hidden from the main list view")
    
    # Message cache fields
    first_message = models.ForeignKey('unicom.Message', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    first_outgoing_message = models.ForeignKey('unicom.Message', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    first_incoming_message = models.ForeignKey('unicom.Message', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    last_message = models.ForeignKey('unicom.Message', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    last_outgoing_message = models.ForeignKey('unicom.Message', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    last_incoming_message = models.ForeignKey('unicom.Message', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    # accounts = models.ManyToManyField('unicom.Account', related_name="chats")

    def send_message(self, msg_dict: dict, user:User=None) -> Message:
        """
        Send a message to this chat using the channel's platform.
        The msg_dict must include at least the text or media to send.
        
        If reply_to_message_id is provided in msg_dict, it will reply to that specific message.
        For email channels without a specific reply_to_message_id, this will find the last incoming 
        message and reply to it, ensuring proper email threading.
        """
        if not self.channel.active:
            raise ValueError("Channel must be active to send messages.")
        
        try:
            # If replying to a specific message
            if reply_to_id := msg_dict.pop('reply_to_message_id', None):
                from unicom.models import Message
                reply_to_message = Message.objects.get(id=reply_to_id, chat=self)
                return reply_to_message.reply_with(msg_dict)
            
            # Default behavior for email - reply to last incoming message
            elif self.platform == 'Email':
                last_incoming = self.messages.filter(
                    is_outgoing=False
                ).order_by('-timestamp').first()
                
                if not last_incoming:
                    raise ValidationError("No incoming messages found in this email chat to reply to")
                
                return last_incoming.reply_with(msg_dict)
            
            # For other platforms without specific reply
            else:
                from unicom.services.crossplatform.send_message import send_message
                return send_message(self.channel, {**msg_dict, "chat_id": self.id}, user)
                
        except Exception as e:
            raise ValueError(f"Failed to send message: {str(e)}")

    def __str__(self) -> str:
        return f"{self.platform}:{self.id} ({self.name})"