#!/usr/bin/env python
"""Send a test message with buttons to test button functionality"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unicom_project.settings')
django.setup()

from unicom.models import Account, Message
from unicom.services.telegram.create_inline_keyboard import (
    create_inline_keyboard, create_callback_button
)

def send_test_buttons():
    # Get your account
    # Replace with your actual Telegram user ID or username
    account = Account.objects.filter(platform='Telegram').first()

    if not account:
        print("❌ No Telegram account found!")
        return

    username = account.raw.get('username', account.name)
    print(f"📤 Sending test buttons to: {username}")

    # Get the most recent message from this account to use as reference
    recent_msg = Message.objects.filter(
        sender=account,
        channel__platform='Telegram'
    ).order_by('-timestamp').first()

    if not recent_msg:
        print("❌ No recent message found to reply to!")
        return

    # Send test message with buttons
    recent_msg.reply_with({
        "text": "🧪 **Button Test Menu**\n\nClick buttons to test functionality:",
        "reply_markup": create_inline_keyboard([
            [create_callback_button("✏️ Edit Message", {"test": "edit"},
                                   message=recent_msg, account=account)],
            [create_callback_button("💬 Send Reply", {"test": "reply"},
                                   message=recent_msg, account=account)],
            [create_callback_button("🔢 Counter Test", {"test": "counter", "count": 0},
                                   message=recent_msg, account=account)],
            [create_callback_button("📋 Submenu Test", {"test": "submenu"},
                                   message=recent_msg, account=account)]
        ])
    })

    print("✅ Test message sent!")

if __name__ == '__main__':
    send_test_buttons()
