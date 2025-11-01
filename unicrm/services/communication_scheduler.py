from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Tuple

from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from jinja2 import TemplateError

from unicrm.models import Communication, CommunicationMessage, Contact
from unicrm.services.template_renderer import render_template_for_contact, get_jinja_environment


@dataclass
class CommunicationPreparationResult:
    communication: Communication
    created: int
    updated: int
    skipped: int
    errors: list[str]


def _render_subject(subject_template: str, context: dict) -> Tuple[str, list[str]]:
    """
    Render the subject template with the provided context.
    """
    if not subject_template:
        return '', []
    env = get_jinja_environment()
    errors: list[str] = []
    try:
        template = env.from_string(subject_template)
        subject = template.render(context)
    except TemplateError as exc:
        subject = subject_template
        errors.append(str(exc))
    return subject.strip(), errors


def _eligible_contacts(communication: Communication) -> Iterable[Contact]:
    """
    Returns contacts matching the segment; filtering for email happens downstream.
    """
    return communication.segment.apply()


def generate_drafts_for_communication(communication: Communication) -> CommunicationPreparationResult:
    """
    Prepares per-contact payloads for the provided communication.
    """
    if not communication.channel:
        raise ValueError("Communication must define a channel before generating drafts.")

    contacts = list(_eligible_contacts(communication))
    send_at = communication.scheduled_for or timezone.now()
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    for contact in contacts:
        render_result = render_template_for_contact(
            communication.get_renderable_content(),
            contact=contact,
            communication=communication,
        )
        subject_template = (
            communication.subject_template
            or f"Communication {communication.pk}"
        )
        subject, subject_errors = _render_subject(subject_template, render_result.context)
        errors.extend(subject_errors)
        delivery, created_delivery = CommunicationMessage.objects.get_or_create(
            communication=communication,
            contact=contact,
            defaults={'metadata': {}},
        )

        if not contact.email:
            skipped += 1
            delivery.metadata.setdefault('errors', []).append('No email address on contact.')
            delivery.save(update_fields=['metadata', 'updated_at'])
            continue

        if render_result.errors:
            display_errors = delivery.metadata.setdefault('errors', [])
            display_errors.extend(render_result.errors)

        payload = {
            'to': [contact.email],
            'subject': subject or subject_template or f"Communication {communication.pk}",
            'html': render_result.html,
        }

        metadata = delivery.metadata or {}
        metadata['status'] = metadata.get('status', 'pending')
        metadata['send_at'] = send_at.isoformat()
        metadata['payload'] = payload
        metadata['variables'] = json.loads(json.dumps(render_result.variables, cls=DjangoJSONEncoder))
        metadata['context'] = json.loads(json.dumps(render_result.context, cls=DjangoJSONEncoder))
        delivery.metadata = metadata
        delivery.save(update_fields=['metadata', 'updated_at'])

        if created_delivery:
            created += 1
        else:
            updated += 1

    communication.status = 'scheduled'
    communication.scheduled_for = send_at
    communication.save(update_fields=['status', 'scheduled_for', 'updated_at'])
    communication.refresh_status_summary()

    return CommunicationPreparationResult(
        communication=communication,
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )
