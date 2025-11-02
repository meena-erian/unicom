from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from unicom.models import Channel
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
        self.html_content = '<p>Hello <!--mce:protected %7B%7B%20contact.first_name%20%7D%7D-->!</p>'
        self.segment = Segment.objects.create(
            name='All Contacts',
            description='All contacts',
            code="""
def apply(qs):
    return qs
""",
        )

    def test_preparation_creates_payloads(self):
        communication = Communication.objects.create(
            segment=self.segment,
            channel=self.channel,
            initiated_by=self.user,
            scheduled_for=timezone.now() + timedelta(hours=1),
            subject_template="Hello <!--mce:protected %7B%7B%20contact.first_name%20%7D%7D-->",
            content=self.html_content,
        )

        result = generate_drafts_for_communication(communication)

        communication.refresh_from_db()
        self.assertEqual(result.created, 1)
        self.assertEqual(communication.status, 'scheduled')
        self.assertEqual(communication.messages.count(), 1)
        delivery = communication.messages.first()
        payload = delivery.metadata.get('payload')
        self.assertEqual(payload['to'], [self.contact.email])
        self.assertEqual(payload['subject'], 'Hello John')
        self.assertIn('Hello John', payload['html'])
        self.assertEqual(communication.status_summary.get('scheduled'), 1)
        self.assertEqual(communication.status_summary.get('clicked'), 0)

    def test_refresh_summary_updates_when_sent(self):
        communication = Communication.objects.create(
            segment=self.segment,
            channel=self.channel,
            initiated_by=self.user,
            scheduled_for=timezone.now(),
            content=self.html_content,
        )
        generate_drafts_for_communication(communication)

        delivery = communication.messages.first()
        metadata = delivery.metadata or {}
        metadata['status'] = 'sent'
        delivery.metadata = metadata
        delivery.save(update_fields=['metadata'])

        communication.refresh_from_db()
        communication.refresh_status_summary()
        self.assertEqual(communication.status_summary.get('sent'), 1)
        self.assertEqual(communication.status, 'completed')

    def test_contacts_without_email_are_skipped(self):
        contact = Contact.objects.create(
            first_name='NoEmail',
            email='',
        )
        communication = Communication.objects.create(
            segment=self.segment,
            channel=self.channel,
            initiated_by=self.user,
            scheduled_for=timezone.now(),
            content=self.html_content,
        )

        result = generate_drafts_for_communication(communication)

        self.assertEqual(result.skipped, 1)  # the blank email contact
        self.assertEqual(CommunicationMessage.objects.filter(communication=communication).count(), 2)
