from django.db import models
from .constants import channels


class Chat(models.Model):
    id = models.CharField(max_length=500, primary_key=True)
    platform = models.CharField(max_length=100, choices=channels)
    is_private = models.BooleanField(default=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    # accounts = models.ManyToManyField('unicom.Account', related_name="chats")

    def __str__(self) -> str:
        return f"{self.platform}:{self.id} ({self.name})"