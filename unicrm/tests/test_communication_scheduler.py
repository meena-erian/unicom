from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from unicom.models import Channel, MessageTemplate
from unicrm.models import (
    Communication,
    CommunicationMessage,
    Company,
    Contact,
    Segment,
)
from unicrm.services.communication_scheduler import generate_drafts_for_communication


class CommunicationSchedulerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(username='marketing')
        self.company = Company.objects.create(name='Acme Inc.')
        self.contact = Contact.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            company=self.company,
        )
        self.channel = Channel.objects.create(
            name='Email Channel',
            platform='Email',
            config={},
            active=True,
        )
        self.template = MessageTemplate.objects.create(
            title='Welcome Campaign',
            content='<p>Hello {{ contact.first_name }}!</p>',
        )
        self.segment = Segment.objects.create(
            name='All Contacts',
            description='All contacts',
            code="""
def apply(qs):
    return qs
""",
        )

    def test_generate_drafts_creates_communication_messages(self):
        communication = Communication.objects.create(
            template=self.template,
            segment=self.segment,
            channel=self.channel,
            initiated_by=self.user,
            scheduled_for=timezone.now() + timedelta(hours=1),
            subject_template="Hello {{ contact.first_name }}",
        )

        result = generate_drafts_for_communication(communication)

        communication.refresh_from_db()
        self.assertEqual(result.created, 1)
        self.assertEqual(communication.status, 'scheduled')
        self.assertEqual(communication.messages.count(), 1)
        delivery = communication.messages.first()
        self.assertIsNotNone(delivery.draft)
        self.assertEqual(delivery.draft.to, [self.contact.email])
        self.assertEqual(delivery.draft.status, 'scheduled')
        self.assertIn('Hello John', delivery.draft.subject)
        self.assertIn('Hello John', delivery.draft.html)
        self.assertEqual(communication.status_summary.get('scheduled'), 1)

    def test_signal_updates_summary_when_draft_sent(self):
        communication = Communication.objects.create(
            template=self.template,
            segment=self.segment,
            channel=self.channel,
            initiated_by=self.user,
            scheduled_for=timezone.now(),
        )
        generate_drafts_for_communication(communication)

        delivery = communication.messages.first()
        draft = delivery.draft
        draft.status = 'sent'
        draft.save()

        communication.refresh_from_db()
        self.assertEqual(communication.status_summary.get('sent'), 1)
        self.assertEqual(communication.status, 'completed')

    def test_contacts_without_email_are_skipped(self):
        contact = Contact.objects.create(
            first_name='NoEmail',
            email='',
        )
        communication = Communication.objects.create(
            template=self.template,
            segment=self.segment,
            channel=self.channel,
            initiated_by=self.user,
            scheduled_for=timezone.now(),
        )

        result = generate_drafts_for_communication(communication)

        self.assertEqual(result.skipped, 1)  # the blank email contact
        self.assertEqual(CommunicationMessage.objects.filter(communication=communication).count(), 2)
