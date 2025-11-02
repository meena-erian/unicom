from __future__ import annotations

from typing import Iterable

from django.contrib.auth import get_user_model

from django.db.models.signals import post_delete, post_migrate, post_save
from django.dispatch import receiver

from unicom.models import Message
from unicrm.models import CommunicationMessage
from unicrm.seed_data import ensure_default_segments
from unicrm.services.user_contact_sync import (
    ensure_contact_for_user,
    sync_all_user_contacts,
)


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


@receiver(post_save, sender=Message)
def message_saved(sender, instance: Message, **kwargs):
    linked = list(CommunicationMessage.objects.filter(message=instance))
    _refresh_communications(linked)


@receiver(post_migrate)
def create_default_segments(sender, **kwargs):
    if sender.label != 'unicrm':
        return

    ensure_default_segments()
    sync_all_user_contacts()


UserModel = get_user_model()


@receiver(post_save, sender=UserModel)
def user_saved(sender, instance, **kwargs):
    ensure_contact_for_user(instance)
