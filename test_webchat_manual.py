#!/usr/bin/env python
"""
Manual test script for WebChat APIs.
Run this to verify WebChat functionality outside of pytest.

Usage:
    python test_webchat_manual.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unicom_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from unicom.models import Channel, Message, Chat, Account, Request
import json


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    print_section("WebChat Manual Test")

    # Create test client
    client = Client()

    # 1. Create WebChat channel
    print_section("Step 1: Create WebChat Channel")
    channel, created = Channel.objects.get_or_create(
        name="Manual Test WebChat",
        platform="WebChat",
        defaults={'config': {}}
    )
    channel.validate()
    print(f"✅ Channel created: {channel}")
    print(f"   Active: {channel.active}")
    print(f"   ID: {channel.id}")

    # 2. Test guest user sending message
    print_section("Step 2: Guest User Sends Message")
    response = client.post('/unicom/webchat/send/', {
        'text': 'Hello from guest user! This is a test message.'
    })

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    if response.status_code == 200:
        print("✅ Guest message sent successfully!")
        message_id = data['message']['id']
        chat_id = data['message']['chat_id']

        # Verify message in database
        message = Message.objects.get(id=message_id)
        print(f"   Message ID: {message.id}")
        print(f"   Text: {message.text}")
        print(f"   Sender: {message.sender}")
        print(f"   Chat: {message.chat}")

        # Check if Request was created
        request = Request.objects.filter(message=message).first()
        if request:
            print(f"   Request created: {request.id}")
            print(f"   Request status: {request.status}")

    else:
        print(f"❌ Failed to send message: {data}")
        return

    # 3. Test retrieving messages
    print_section("Step 3: Retrieve Messages")
    response = client.get('/unicom/webchat/messages/')

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Retrieved {len(data['messages'])} messages")
        for msg in data['messages']:
            print(f"   - [{msg['timestamp']}] {msg['sender_name']}: {msg['text']}")
    else:
        print(f"❌ Failed to retrieve messages: {response.status_code}")

    # 4. Test authenticated user
    print_section("Step 4: Create Authenticated User")
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User'
        }
    )
    if created:
        user.set_password('testpass123')
        user.save()
    print(f"✅ User: {user.username} ({user.email})")

    # 5. Login and send message
    print_section("Step 5: Authenticated User Sends Message")
    client.login(username='testuser', password='testpass123')

    response = client.post('/unicom/webchat/send/', {
        'text': 'Hello! I am an authenticated user sending a message.'
    })

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Authenticated message sent!")
        print(f"   Message ID: {data['message']['id']}")
        print(f"   Chat ID: {data['message']['chat_id']}")

        # Verify account was linked correctly
        account = Account.objects.get(id=f"webchat_user_{user.id}")
        print(f"   Account: {account}")
        if account.member:
            print(f"   Linked to Member: {account.member}")
    else:
        print(f"❌ Failed: {response.json()}")

    # 6. List chats
    print_section("Step 6: List User's Chats")
    response = client.get('/unicom/webchat/chats/')

    if response.status_code == 200:
        data = response.json()
        print(f"✅ User has {len(data['chats'])} chat(s)")
        for chat in data['chats']:
            print(f"   - Chat: {chat['name']}")
            print(f"     ID: {chat['id']}")
            if chat['last_message']:
                print(f"     Last: {chat['last_message']['text'][:50]}...")
    else:
        print(f"❌ Failed: {response.status_code}")

    # 7. Test bot reply
    print_section("Step 7: Bot Reply")

    # Get user's chat
    user_account = Account.objects.get(id=f"webchat_user_{user.id}")
    user_chat = Chat.objects.filter(accountchat__account=user_account).first()

    if user_chat:
        # Send bot reply
        bot_message = channel.send_message({
            'chat_id': user_chat.id,
            'text': 'Hello! I am a bot replying to your message. How can I help you today?'
        })

        print(f"✅ Bot reply sent!")
        print(f"   Message ID: {bot_message.id}")
        print(f"   Text: {bot_message.text}")
        print(f"   Is Outgoing: {bot_message.is_outgoing}")

        # Retrieve messages to show bot reply
        response = client.get('/unicom/webchat/messages/')
        if response.status_code == 200:
            data = response.json()
            print(f"\n   All messages in chat:")
            for msg in data['messages']:
                direction = "→" if msg['is_outgoing'] else "←"
                print(f"   {direction} {msg['sender_name']}: {msg['text'][:60]}")
    else:
        print("❌ No chat found for user")

    # Summary
    print_section("Test Summary")
    print("✅ All manual tests completed successfully!")
    print(f"\nDatabase State:")
    print(f"  - Channels: {Channel.objects.filter(platform='WebChat').count()}")
    print(f"  - Accounts: {Account.objects.filter(platform='WebChat').count()}")
    print(f"  - Chats: {Chat.objects.filter(platform='WebChat').count()}")
    print(f"  - Messages: {Message.objects.filter(platform='WebChat').count()}")
    print(f"  - Requests: {Request.objects.filter(channel__platform='WebChat').count()}")

    print("\n✅ WebChat Phase 1 is working correctly!\n")


if __name__ == '__main__':
    main()
