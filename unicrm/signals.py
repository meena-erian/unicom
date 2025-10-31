from __future__ import annotations

from typing import Iterable

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from unicom.models import DraftMessage, Message
from unicrm.models import CommunicationMessage


def _affected_communications(messages: Iterable[CommunicationMessage]):
    seen = set()
    for item in messages:
        if item.communication_id in seen:
            continue
        seen.add(item.communication_id)
        yield item.communication


def _refresh_communications(objs: Iterable[CommunicationMessage]):
    for communication in _affected_communications(objs):
        communication.refresh_status_summary()


@receiver(post_save, sender=CommunicationMessage)
def communication_message_saved(sender, instance: CommunicationMessage, **kwargs):
    _refresh_communications([instance])


@receiver(post_delete, sender=CommunicationMessage)
def communication_message_deleted(sender, instance: CommunicationMessage, **kwargs):
    _refresh_communications([instance])


@receiver(post_save, sender=DraftMessage)
def draft_message_saved(sender, instance: DraftMessage, **kwargs):
    linked = list(CommunicationMessage.objects.filter(draft=instance))
    if instance.sent_message_id:
        CommunicationMessage.objects.filter(draft=instance, message__isnull=True).update(message=instance.sent_message)
        linked = list(CommunicationMessage.objects.filter(draft=instance))
    _refresh_communications(linked)


@receiver(post_save, sender=Message)
def message_saved(sender, instance: Message, **kwargs):
    linked = list(CommunicationMessage.objects.filter(message=instance))
    _refresh_communications(linked)

