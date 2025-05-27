from __future__ import annotations
from typing import TYPE_CHECKING
from django.db import models
from .constants import channels
from unicom.services.crossplatform.send_message import send_message
from django.contrib.auth.models import User

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
        """
        if not self.channel.active:
            raise ValueError("Channel must be active to send messages.")
        
        try:
            return send_message(self.channel, {**msg_dict, "chat_id": self.id}, user)
        except Exception as e:
            raise ValueError(f"Failed to send message: {str(e)}")

    def __str__(self) -> str:
        return f"{self.platform}:{self.id} ({self.name})"