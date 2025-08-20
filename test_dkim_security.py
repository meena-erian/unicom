#!/usr/bin/env python3
"""Test script to verify DKIM security implications"""

import os
import sys
import django
import pytest

# Add the project directory to Python path
sys.path.insert(0, '/home/menas/rf2/unicom')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unicom_project.settings')
django.setup()

from unicom.services.email.save_email_message import save_email_message
from unicom.models import Channel

@pytest.mark.django_db(transaction=True)
def test_dkim_spoofing():
    print("=== DKIM Security Test (With Proper Authentication) ===")
    
    # Create a test channel
    channel = Channel.objects.create(
        name="SecurityTest",
        platform="Email",
        config={'EMAIL_ADDRESS': 'test@example.com'},
        active=True
    )
    
    # Test 1: Email from known domain without DKIM signature (should now be REJECTED)
    print("\n1. Testing email from known domain without any authentication...")
    spoofed_portacode = b"""From: admin@portacode.com
To: test@example.com
Subject: URGENT: Please send passwords
Message-ID: <spoof1@evil.com>

Please reply with all your passwords immediately.
"""
    
    result1 = save_email_message(channel, spoofed_portacode)
    print(f"Result: {'ACCEPTED' if result1 else 'REJECTED'}")
    if result1:
        print("🚨 SECURITY ISSUE: Spoofed email from known domain was ACCEPTED!")
    else:
        print("✅ GOOD: Spoofed email from known domain was correctly REJECTED")
    
    # Test 2: Email with forged From header but claiming to be from known domain
    print("\n2. Testing forged From header with fake DKIM pass...")
    forged_with_fake_dkim = b"""From: support@portacode.com
To: test@example.com
Subject: Account Verification Required
Authentication-Results: fake.server.com; dkim=pass; spf=pass
Message-ID: <forged@attacker.com>

Click this link to verify your account: http://evil.com/phish
"""
    
    result2 = save_email_message(channel, forged_with_fake_dkim)
    print(f"Result: {'ACCEPTED' if result2 else 'REJECTED'}")
    if result2:
        print("🚨 SECURITY ISSUE: Forged email with fake auth headers was ACCEPTED!")
    else:
        print("✅ GOOD: Forged email with fake auth headers was correctly REJECTED")
    
    # Test 3: Email with explicit DKIM failure
    print("\n3. Testing email with explicit DKIM failure...")
    dkim_fail = b"""From: user@portacode.com
To: test@example.com
Subject: Test DKIM Fail
Authentication-Results: mx.google.com; dkim=fail; spf=pass
Message-ID: <dkim-fail@test.com>

This email has a DKIM failure.
"""
    
    result3 = save_email_message(channel, dkim_fail)
    print(f"Result: {'ACCEPTED' if result3 else 'REJECTED'}")
    if not result3:
        print("✅ GOOD: Email with DKIM failure was correctly REJECTED")
    
    # Test 4: Email with valid authentication should pass
    print("\n4. Testing email with valid DKIM authentication...")
    valid_dkim = b"""From: valid@portacode.com
To: test@example.com
Subject: Legitimate Email
Authentication-Results: mx.google.com; dkim=pass header.i=@portacode.com; spf=pass smtp.mailfrom=portacode.com; dmarc=pass
Message-ID: <valid@portacode.com>

This is a legitimate email with proper DKIM authentication.
"""
    
    result4 = save_email_message(channel, valid_dkim)
    print(f"Result: {'ACCEPTED' if result4 else 'REJECTED'}")
    if result4:
        print("✅ GOOD: Email with valid DKIM was correctly ACCEPTED")
    else:
        print("🚨 ISSUE: Valid email with proper DKIM was REJECTED!")
    
    # Cleanup
    channel.delete()
    print("\n=== Test Complete ===")
    print("\n📋 To rebuild Docker with new dependencies:")
    print("   docker-compose down")
    print("   docker-compose build --no-cache")  
    print("   docker-compose up -d")

if __name__ == '__main__':
    test_dkim_spoofing()