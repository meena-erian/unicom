import time
import pytest
import smtplib
import socket
from email.mime.text import MIMEText
from django.test import Client
from django.utils import timezone
from django.db import transaction, connections

from unicom.models import (
    Channel,
    Member,
    Request,
    RequestCategory,
    Message,
)
from tests.utils import wait_for_condition
from tests.email_credentials import EMAIL_CONFIG, EMAIL_CONFIG2, EMAIL_CONFIG3


def send_test_email(from_config, to_address, subject, body, timeout=10):
    """Helper function to send test emails using SMTP"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_config['EMAIL_ADDRESS']
    msg['To'] = to_address

    smtp_config = from_config['SMTP']
    try:
        # Create SMTP connection with timeout
        if smtp_config.get('use_ssl', True):
            server = smtplib.SMTP_SSL(smtp_config['host'], smtp_config['port'], timeout=timeout)
        else:
            server = smtplib.SMTP(smtp_config['host'], smtp_config['port'], timeout=timeout)
            server.starttls(timeout=timeout)
            
        try:
            server.login(from_config['EMAIL_ADDRESS'], from_config['EMAIL_PASSWORD'])
            server.send_message(msg)
        finally:
            server.quit()
    except (socket.timeout, smtplib.SMTPServerDisconnected) as e:
        raise TimeoutError(f"SMTP operation timed out: {str(e)}")


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestEmailRequestProcessing:
    @pytest.fixture(autouse=True)
    def setup(self, db):
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser(
            username='admin', email=EMAIL_CONFIG['EMAIL_ADDRESS'], password='password'
        )
        self.client = Client()

        # Create the main channel that will receive emails
        with transaction.atomic():
            self.channel = Channel.objects.create(
                name="EmailRequestTest",
                platform="Email",
                config=EMAIL_CONFIG,
                active=True  # Set active to True since we're testing
            )
            
            # Verify the channel was created
            self.channel.refresh_from_db()
            assert self.channel.pk is not None, "Channel was not properly created"
            
            # Create a member for one of the senders
            self.member = Member.objects.create(
                name="Test Member",
                email=EMAIL_CONFIG2['EMAIL_ADDRESS']
            )

            # Store the non-member email for comparison
            self.non_member_email = EMAIL_CONFIG3['EMAIL_ADDRESS']

    def _wait_bot(self, pk, *, cond, timeout=60):
        """Wait for bot to be in desired state"""
        def check_condition():
            try:
                channel = Channel.objects.get(pk=pk)
                return cond(channel)
            except Channel.DoesNotExist:
                return False
                
        return wait_for_condition(check_condition, timeout=timeout)

    def _wait_request(self, *, cond, timeout=60):
        """Wait for a request matching the condition"""
        def check_condition():
            try:
                # If cond is a dict of filter conditions, use it directly
                exists = Request.objects.filter(**cond).exists()
                if not exists:
                    # Print current state for debugging
                    email = cond.get('email')
                    if email:
                        reqs = Request.objects.filter(email=email)
                        for req in reqs:
                            print(f"Request {req.id} status: {req.status}")
                return exists
            except Exception as e:
                print(f"Error in check_condition: {e}")
                return False
                
        return wait_for_condition(check_condition, timeout=timeout)

    def test_request_creation_no_categories(self):
        """Test request creation when there are no categories in the system"""
        # Send test email from member
        send_test_email(
            EMAIL_CONFIG2,
            EMAIL_CONFIG['EMAIL_ADDRESS'],
            "Test Request - Member",
            "This is a test request from a member"
        )

        # Wait for request and verify it's properly identified
        self._wait_request(cond={'email': EMAIL_CONFIG2['EMAIL_ADDRESS']})
        request = Request.objects.filter(email=EMAIL_CONFIG2['EMAIL_ADDRESS']).order_by('-created_at').first()
        assert request.member == self.member
        assert request.status == 'QUEUED'  # Should be queued even without categories
        assert request.category is None

        # Send test email from non-member
        send_test_email(
            EMAIL_CONFIG3,
            EMAIL_CONFIG['EMAIL_ADDRESS'],
            "Test Request - Non-Member",
            "This is a test request from a non-member"
        )

        # Wait for request and verify it's properly handled
        self._wait_request(cond={'email': EMAIL_CONFIG3['EMAIL_ADDRESS']})
        request = Request.objects.filter(email=EMAIL_CONFIG3['EMAIL_ADDRESS']).order_by('-created_at').first()
        assert request.member is None
        assert request.status == 'QUEUED'
        assert request.category is None
        connections.close_all()

    def test_request_with_public_category(self):
        """Test request processing with a public category"""
        # Create a public category
        public_cat = RequestCategory.objects.create(
            name="Public Support",
            sequence=1,
            is_public=True,
            processing_function="""
def process(request, metadata):
    # Match all requests for this test
    return {'category_match': True}
"""
        )

        # Send test emails from both member and non-member
        send_test_email(
            EMAIL_CONFIG2,
            EMAIL_CONFIG['EMAIL_ADDRESS'],
            "Test Public Category - Member",
            "This is a test request for public category from member"
        )
        send_test_email(
            EMAIL_CONFIG3,
            EMAIL_CONFIG['EMAIL_ADDRESS'],
            "Test Public Category - Non-Member",
            "This is a test request for public category from non-member"
        )

        # Wait for and verify both requests
        self._wait_request(cond={'email': EMAIL_CONFIG2['EMAIL_ADDRESS']})
        self._wait_request(cond={'email': EMAIL_CONFIG3['EMAIL_ADDRESS']})

        # Check member request
        member_request = Request.objects.get(email=EMAIL_CONFIG2['EMAIL_ADDRESS'])
        assert member_request.member == self.member
        assert member_request.status == 'QUEUED'
        assert member_request.category == public_cat

        # Check non-member request
        non_member_request = Request.objects.get(email=EMAIL_CONFIG3['EMAIL_ADDRESS'])
        assert non_member_request.member is None
        assert non_member_request.status == 'QUEUED'
        assert non_member_request.category == public_cat
        connections.close_all()

    def test_request_with_member_only_category(self):
        """Test request processing with a member-only category"""
        # Create a member-only category
        member_cat = RequestCategory.objects.create(
            name="Member Support",
            sequence=1,
            is_public=False,
            processing_function="""
def process(request, metadata):
    # Match all requests for this test
    return {'category_match': True}
"""
        )
        member_cat.authorized_members.add(self.member)

        # Send test emails from both member and non-member
        send_test_email(
            EMAIL_CONFIG2,
            EMAIL_CONFIG['EMAIL_ADDRESS'],
            "Test Member Category",
            "This is a test request for member category"
        )
        send_test_email(
            EMAIL_CONFIG3,
            EMAIL_CONFIG['EMAIL_ADDRESS'],
            "Test Member Category - Non-Member",
            "This is a test request for member category from non-member"
        )

        # Wait for and verify both requests
        self._wait_request(cond={'email': EMAIL_CONFIG2['EMAIL_ADDRESS']})
        self._wait_request(cond={'email': EMAIL_CONFIG3['EMAIL_ADDRESS']})

        # Check member request
        member_request = Request.objects.get(email=EMAIL_CONFIG2['EMAIL_ADDRESS'])
        assert member_request.member == self.member
        assert member_request.status == 'QUEUED'
        assert member_request.category == member_cat

        # Check non-member request
        non_member_request = Request.objects.get(email=EMAIL_CONFIG3['EMAIL_ADDRESS'])
        assert non_member_request.member is None
        assert non_member_request.status == 'QUEUED'
        assert non_member_request.category is None  # Should not get member-only category
        connections.close_all()

    def test_request_with_hierarchical_categories(self):
        """Test request processing with hierarchical categories"""
        print("\n=== Starting hierarchical categories test ===")
        
        # Create parent category (public)
        parent_cat = RequestCategory.objects.create(
            name="Support",
            sequence=1,
            is_public=True,
            processing_function="""
def process(request, metadata):
    print(f"Processing parent category for request {request.id}")
    return {'category_match': True}
"""
        )
        print(f"Created parent category: {parent_cat.name} (id={parent_cat.id})")

        # Create child category (member-only)
        child_cat = RequestCategory.objects.create(
            name="Premium Support",
            parent=parent_cat,
            sequence=1,
            is_public=False,
            processing_function="""
def process(request, metadata):
    print(f"Processing child category for request {request.id}")
    return {'category_match': True}
"""
        )
        child_cat.authorized_members.add(self.member)
        print(f"Created child category: {child_cat.name} (id={child_cat.id})")
        print(f"Added member {self.member.email} to child category")

        # Send test emails
        print("\nSending test emails...")
        send_test_email(
            EMAIL_CONFIG2,
            EMAIL_CONFIG['EMAIL_ADDRESS'],
            "Test Hierarchical Categories - Member",
            "This is a test request for hierarchical categories from member"
        )
        print(f"Sent member email from {EMAIL_CONFIG2['EMAIL_ADDRESS']}")
        
        send_test_email(
            EMAIL_CONFIG3,
            EMAIL_CONFIG['EMAIL_ADDRESS'],
            "Test Hierarchical Categories - Non-Member",
            "This is a test request for hierarchical categories from non-member"
        )
        print(f"Sent non-member email from {EMAIL_CONFIG3['EMAIL_ADDRESS']}")

        print("\nWaiting for requests to be processed...")
        # Wait for requests to be created and reach final status
        self._wait_request(cond={'email': EMAIL_CONFIG2['EMAIL_ADDRESS'], 'status': 'QUEUED'})
        self._wait_request(cond={'email': EMAIL_CONFIG3['EMAIL_ADDRESS'], 'status': 'QUEUED'})

        # Check member request
        print("\nChecking member request...")
        member_request = Request.objects.get(email=EMAIL_CONFIG2['EMAIL_ADDRESS'])
        print(f"Member request status: {member_request.status}")
        print(f"Member request category: {member_request.category.name if member_request.category else 'None'}")
        assert member_request.member == self.member
        assert member_request.status == 'QUEUED'
        assert member_request.category == child_cat  # Should get child category

        # Check non-member request
        print("\nChecking non-member request...")
        non_member_request = Request.objects.get(email=EMAIL_CONFIG3['EMAIL_ADDRESS'])
        print(f"Non-member request status: {non_member_request.status}")
        print(f"Non-member request category: {non_member_request.category.name if non_member_request.category else 'None'}")
        assert non_member_request.member is None
        assert non_member_request.status == 'QUEUED'
        assert non_member_request.category == parent_cat  # Should only get parent category 
        connections.close_all()