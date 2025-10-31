from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Tuple

from django.db import transaction
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from jinja2 import TemplateError

from unicom.models import DraftMessage
from unicrm.models import Communication, CommunicationMessage, Contact
from unicrm.services.template_renderer import render_template_for_contact, get_jinja_environment


@dataclass
class DraftCreationResult:
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


@transaction.atomic
def generate_drafts_for_communication(communication: Communication) -> DraftCreationResult:
    """
    Creates or updates DraftMessages and CommunicationMessages for the provided communication.
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
            communication.template.content,
            contact=contact,
            communication=communication,
        )
        subject_template = (
            communication.subject_template
            or communication.template.title
            or communication.template.description
            or f"Communication {communication.pk}"
        )
        subject, subject_errors = _render_subject(subject_template, render_result.context)
        errors.extend(subject_errors)
        delivery, created_delivery = CommunicationMessage.objects.select_for_update().get_or_create(
            communication=communication,
            contact=contact,
            defaults={'metadata': {}},
        )
        draft = delivery.draft

        if not contact.email:
            skipped += 1
            delivery.metadata.setdefault('errors', []).append('No email address on contact.')
            delivery.save(update_fields=['metadata', 'updated_at'])
            continue

        if render_result.errors:
            display_errors = delivery.metadata.setdefault('errors', [])
            display_errors.extend(render_result.errors)

        draft_kwargs = {
            'channel': communication.channel,
            'to': [contact.email],
            'subject': subject or communication.template.title or communication.template.description or f"Campaign {communication.pk}",
            'html': render_result.html,
            'status': 'scheduled',
            'is_approved': True,
            'send_at': send_at,
            'created_by': communication.initiated_by,
        }
        if draft:
            for field, value in draft_kwargs.items():
                setattr(draft, field, value)
            draft.save()
            updated += 1
        else:
            draft = DraftMessage.objects.create(**draft_kwargs)
            created += 1

        delivery.draft = draft
        delivery.metadata['variables'] = json.loads(json.dumps(render_result.variables, cls=DjangoJSONEncoder))
        delivery.metadata['context'] = json.loads(json.dumps(render_result.context, cls=DjangoJSONEncoder))
        delivery.save(update_fields=['draft', 'metadata', 'updated_at'])

    communication.status = 'scheduled'
    communication.scheduled_for = send_at
    communication.save(update_fields=['status', 'scheduled_for', 'updated_at'])
    communication.refresh_status_summary()

    return DraftCreationResult(
        communication=communication,
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )
