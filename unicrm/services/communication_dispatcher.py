from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction

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


def process_scheduled_communications(now=None, verbosity: int = 0) -> Dict[str, int]:
    """Send drafts for communications scheduled and due."""
    summary = CommunicationDispatchSummary()

    current_time = now or timezone.now()
    due_ids = list(
        Communication.objects
        .filter(status='scheduled', scheduled_for__isnull=False, scheduled_for__lte=current_time)
        .values_list('id', flat=True)
    )

    details: List[Dict[str, Any]] = []

    for communication_id in due_ids:
        with transaction.atomic():
            try:
                communication = (
                    Communication.objects
                    .select_for_update(skip_locked=True)
                    .get(pk=communication_id)
                )
            except Communication.DoesNotExist:
                continue

            if (
                communication.status != 'scheduled'
                or communication.scheduled_for is None
                or communication.scheduled_for > current_time
            ):
                continue

            summary.communications_examined += 1

            if not communication.channel:
                logger.warning(
                    "Communication %s has no channel assigned; skipping dispatch.",
                    communication.pk,
                )
                details.append({
                    'communication_id': communication.pk,
                    'contact_id': None,
                    'contact_email': None,
                    'status': 'skipped',
                    'subject': None,
                    'html': None,
                    'errors': ['Channel missing'],
                    'note': 'no_channel',
                })
                continue

            # Refresh payloads on every run to keep template output current.
            generate_drafts_for_communication(communication)

            deliveries = list(
                communication.messages.select_for_update(skip_locked=True).select_related('contact')
            )

            sent = 0
            failed = 0

            for delivery in deliveries:
                metadata: Dict[str, Any] = delivery.metadata or {}
                payload: Dict[str, Any] = metadata.get('payload') or {}

                record: Dict[str, Any] = {
                    'communication_id': communication.pk,
                    'contact_id': delivery.contact_id,
                    'contact_email': getattr(delivery.contact, 'email', None),
                    'status': metadata.get('status', 'pending'),
                    'subject': payload.get('subject'),
                    'html': payload.get('html'),
                    'errors': list(metadata.get('errors', [])),
                }

                send_at_str = metadata.get('send_at')
                send_at_dt = parse_datetime(send_at_str) if send_at_str else None
                if send_at_dt and send_at_dt > current_time:
                    record['note'] = 'scheduled_in_future'
                    details.append(record)
                    continue

                if record['status'] in {'sent', 'failed'}:
                    record['note'] = f"already_{record['status']}"
                    details.append(record)
                    continue

                if not payload:
                    record['note'] = 'no_payload'
                    details.append(record)
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
                    record['status'] = 'sent'
                    record['errors'] = []
                except Exception as exc:  # pragma: no cover - defensive
                    metadata.setdefault('errors', []).append(str(exc))
                    metadata['status'] = 'failed'
                    failed += 1
                    record['status'] = 'failed'
                    record.setdefault('errors', []).append(str(exc))
                    logger.exception(
                        "Failed sending payload for communication %s (contact %s).",
                        communication.pk,
                        delivery.contact_id,
                    )

                delivery.metadata = metadata
                delivery.save(update_fields=['metadata', 'message', 'updated_at'])
                details.append(record)

            if sent or failed:
                summary.communications_processed += 1
                summary.messages_sent += sent
                summary.messages_failed += failed

            communication.refresh_status_summary()

    result = summary.to_dict()
    result['details'] = details
    return result
