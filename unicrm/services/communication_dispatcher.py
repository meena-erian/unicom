from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from django.utils import timezone

from django.utils.dateparse import parse_datetime

from unicrm.models import Communication, CommunicationMessage

from unicrm.services.communication_scheduler import generate_drafts_for_communication

MessageModel = CommunicationMessage._meta.get_field('message').remote_field.model

logger = logging.getLogger(__name__)


@dataclass
class CommunicationDispatchSummary:
    communications_examined: int = 0
    communications_processed: int = 0
    messages_sent: int = 0
    messages_failed: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            'communications_examined': self.communications_examined,
            'communications_processed': self.communications_processed,
            'messages_sent': self.messages_sent,
            'messages_failed': self.messages_failed,
        }


def process_scheduled_communications(now=None) -> Dict[str, int]:
    """Send drafts for communications scheduled and due."""
    summary = CommunicationDispatchSummary()

    current_time = now or timezone.now()

    due_queryset = (
        Communication.objects
        .filter(status='scheduled', scheduled_for__isnull=False, scheduled_for__lte=current_time)
        .select_related('channel')
        .order_by('scheduled_for')
    )

    for communication in due_queryset:
        summary.communications_examined += 1

        if not communication.channel:
            logger.warning(
                "Communication %s has no channel assigned; skipping dispatch.",
                communication.pk,
            )
            continue

        if not communication.messages.exists():
            generate_drafts_for_communication(communication)

        deliveries = list(
            communication.messages.select_related('message')
        )

        sent = 0
        failed = 0

        for delivery in deliveries:
            metadata = delivery.metadata or {}
            status = metadata.get('status', 'pending')

            if status == 'sent':
                continue

            payload = metadata.get('payload')
            if not payload:
                continue

            send_at_str = metadata.get('send_at')
            if send_at_str:
                send_at_dt = parse_datetime(send_at_str)
                if send_at_dt and send_at_dt > current_time:
                    continue

            try:
                message_instance = communication.channel.send_message(
                    payload,
                    user=communication.initiated_by,
                )
                metadata['status'] = 'sent'
                metadata.pop('errors', None)
                if isinstance(message_instance, MessageModel):
                    delivery.message = message_instance
                sent += 1
            except Exception as exc:  # pragma: no cover - defensive
                metadata.setdefault('errors', []).append(str(exc))
                metadata['status'] = 'failed'
                failed += 1
                logger.exception(
                    "Failed sending payload for communication %s (contact %s).",
                    communication.pk,
                    delivery.contact_id,
                )

            delivery.metadata = metadata
            delivery.save(update_fields=['metadata', 'message', 'updated_at'])

        if sent or failed:
            summary.communications_processed += 1
            summary.messages_sent += sent
            summary.messages_failed += failed

        communication.refresh_status_summary()

    return summary.to_dict()
