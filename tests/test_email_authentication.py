import time
import pytest
import smtplib
import socket
from email.mime.text import MIMEText
from email import policy, message_from_bytes
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import transaction

from unicom.models import Channel, Message, Account, Request, Member
from unicom.services.email.save_email_message import save_email_message, _is_email_authenticated, _basic_email_check
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
class TestEmailAuthentication(TestCase):
    """Test email authentication functionality with real email credentials"""
    
    def setUp(self):
        """Set up test fixtures using real email credentials"""
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser(
            username='admin', email=EMAIL_CONFIG['EMAIL_ADDRESS'], password='password'
        )
        
        # Create the main channel that will receive emails (like existing tests)
        with transaction.atomic():
            self.channel = Channel.objects.create(
                name="EmailAuthTest",
                platform="Email",
                config=EMAIL_CONFIG,
                active=True
            )
            
            # Verify the channel was created and refresh from DB
            self.channel.refresh_from_db()
            assert self.channel.pk is not None, "Channel was not properly created"
            
            # Create a member for testing
            self.member = Member.objects.create(
                name="Test Member",
                email=EMAIL_CONFIG2['EMAIL_ADDRESS']
            )

    def tearDown(self):
        """Clean up after tests"""
        # Clean up is handled by Django's test framework
        pass

    def _wait_request(self, *, cond, timeout=60):
        """Wait for a request matching the condition (copied from existing tests)"""
        def check_condition():
            try:
                return Request.objects.filter(**cond).exists()
            except Exception as e:
                print(f"Error in check_condition: {e}")
                return False
                
        return wait_for_condition(check_condition, timeout=timeout)

    def test_legitimate_email_passes_auth(self):
        """Test that legitimate emails from real domains pass authentication"""
        # Create a legitimate email from a known domain with proper authentication headers
        legitimate_email = f"""From: {EMAIL_CONFIG2['EMAIL_ADDRESS']}
To: {EMAIL_CONFIG['EMAIL_ADDRESS']}
Subject: Test Legitimate Email
Authentication-Results: mx.yandex.ru; spf=pass smtp.mailfrom=portacode.com; dkim=pass header.i=@portacode.com
Message-ID: <legit-auth-test@portacode.com>

This is a legitimate email from a known domain with proper authentication.
""".encode()
        
        # Process the email directly - this tests real authentication
        message = save_email_message(self.channel, legitimate_email)
        
        # Verify message was created successfully (legitimate domain should pass)
        self.assertIsNotNone(message, "Legitimate email from known domain should be processed")
        self.assertEqual(message.sender.id, EMAIL_CONFIG2['EMAIL_ADDRESS'])
        
        # Verify it's not marked as outgoing
        self.assertFalse(message.is_outgoing, "Email should not be marked as outgoing")

    def test_spoofed_email_rejected(self):
        """Test that emails with forged headers are rejected by real authentication"""
        # Create an email that claims to be from insightifyr.com but has failing auth headers
        # This simulates what would happen if someone tried to spoof the domain
        fake_email = f"""From: spoofed@insightifyr.com
To: {EMAIL_CONFIG['EMAIL_ADDRESS']}
Subject: Spoofed Email Test
Message-ID: <spoofed-test@fake.com>
Authentication-Results: yandex.ru; spf=fail smtp.mailfrom=evil.com; dkim=fail header.i=@evil.com; dmarc=fail header.from=insightifyr.com

This is a spoofed email that should be rejected by authentication checks.
""".encode()
        
        # Process the fake email directly - this will use REAL authentication
        message = save_email_message(self.channel, fake_email)
        
        # Verify message was rejected
        self.assertIsNone(message, "Spoofed email should be rejected")
        
        # Verify no objects were created for the spoofed sender
        self.assertFalse(Account.objects.filter(id='spoofed@insightifyr.com').exists())
        self.assertFalse(Message.objects.filter(sender__id='spoofed@insightifyr.com').exists())

    def test_outgoing_emails_bypass_auth(self):
        """Test that outgoing emails (from our bot) bypass authentication"""
        # Create email from our bot's address  
        outgoing_email = f"""From: {EMAIL_CONFIG['EMAIL_ADDRESS']}
To: user@example.com
Subject: Outgoing Email
Message-ID: <outgoing-test@portacode.com>

This is an outgoing email from our system.
""".encode()
        
        # Should be processed without authentication checks
        message = save_email_message(self.channel, outgoing_email)
        self.assertIsNotNone(message)
        self.assertTrue(message.is_outgoing)

    def test_basic_fallback_authentication(self):
        """Test the basic fallback authentication when authheaders fails"""
        # Test email with authentication failure headers (like Yandex might add)
        failing_email = f"""From: attacker@evil.com
To: {EMAIL_CONFIG['EMAIL_ADDRESS']}
Subject: Malicious Email
Authentication-Results: yandex.ru; spf=fail; dkim=fail
Message-ID: <evil-test@evil.com>

This should be rejected by fallback authentication.
""".encode()
        
        # Parse email and test basic check function directly
        msg = message_from_bytes(failing_email, policy=policy.default)
        result = _basic_email_check(msg, 'attacker@evil.com')
        self.assertFalse(result)

    def test_authheaders_library_fallback(self):
        """Test fallback authentication using real Authentication-Results headers"""
        # Test an email with real failing authentication headers from a mail server
        # This tests the _basic_email_check fallback function
        failing_email = f"""From: spoof@fake.com
To: {EMAIL_CONFIG['EMAIL_ADDRESS']}
Subject: Should Be Rejected  
Authentication-Results: mx.yandex.ru; spf=fail smtp.mailfrom=fake.com; dkim=none; dmarc=fail header.from=fake.com
Received: from evil.server.com ([192.168.1.100]) by mx.yandex.ru
Message-ID: <fallback-test@fake.com>

This should be rejected by authentication fallback checks.
""".encode()
        
        # This will use real authentication and should reject the email
        message = save_email_message(self.channel, failing_email)
        self.assertIsNone(message, "Email with failing auth headers should be rejected")
        
        # Test an email with mixed results - some pass, some fail (should still reject)
        mixed_auth_email = f"""From: mixed@fake.com  
To: {EMAIL_CONFIG['EMAIL_ADDRESS']}
Subject: Mixed Auth Results
Authentication-Results: mx.google.com; spf=pass; dkim=fail; dmarc=fail
Message-ID: <mixed-auth@fake.com>

This has mixed authentication results.
""".encode()
        
        message = save_email_message(self.channel, mixed_auth_email)
        self.assertIsNone(message, "Email with any failing auth should be rejected")

    def test_cross_domain_spoofing_attempts(self):
        """Test various cross-domain spoofing attempts that should be rejected"""
        
        # Test 1: Spoofing portacode.com from a different domain
        spoof_portacode = f"""From: admin@portacode.com
To: {EMAIL_CONFIG['EMAIL_ADDRESS']}
Subject: Urgent Account Issue
Authentication-Results: mx.yandex.ru; spf=fail smtp.mailfrom=scammer.com; dkim=fail; dmarc=fail
Message-ID: <spoof-portacode@scammer.com>

Please click this link to verify your account...
""".encode()

        message = save_email_message(self.channel, spoof_portacode)
        self.assertIsNone(message, "Spoofed portacode.com email should be rejected")
        
        # Test 2: Spoofing insightifyr.com with subtle domain variation
        spoof_insightifyr = f"""From: support@insightifyr.com  
To: {EMAIL_CONFIG['EMAIL_ADDRESS']}
Subject: Security Alert
Authentication-Results: smtp.gmail.com; spf=soft-fail smtp.mailfrom=insightlfyr.com; dkim=none
Message-ID: <spoof-insight@phishing.com>

Your account has been compromised...
""".encode()

        message = save_email_message(self.channel, spoof_insightifyr)
        self.assertIsNone(message, "Spoofed insightifyr.com email should be rejected")
        
        # Test 3: Legitimate email with valid authentication headers should pass
        legitimate_email = f"""From: {EMAIL_CONFIG3['EMAIL_ADDRESS']}
To: {EMAIL_CONFIG['EMAIL_ADDRESS']}
Subject: Legitimate Email Test
Authentication-Results: mx.google.com; spf=pass smtp.mailfrom=insightifyr.com; dkim=pass header.i=@insightifyr.com; dmarc=pass
Message-ID: <legit-insight@insightifyr.com>

This is a legitimate email with valid authentication.
""".encode()
        
        # Process legitimate email - should pass authentication
        message = save_email_message(self.channel, legitimate_email)
        self.assertIsNotNone(message, "Legitimate email with valid auth should pass")
        self.assertEqual(message.sender.id, EMAIL_CONFIG3['EMAIL_ADDRESS'])