"""
Cross-platform interactive buttons tests.
Tests button creation, security, and click handling across Telegram and WebChat.
"""
import pytest
from django.test import Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.sessions.backends.db import SessionStore
from datetime import timedelta
import json

from unicom.models import (
    Channel,
    Message,
    Chat,
    Account,
    AccountChat,
    CallbackExecution,
)
from unicom.services.webchat.get_or_create_account import get_or_create_account
from unicom.signals import interactive_button_clicked


@pytest.mark.django_db
class TestCrossPlatformButtons:
    """Test cross-platform interactive button functionality."""

    def setup_method(self):
        """Set up test data."""
        # Create WebChat channel
        self.webchat_channel = Channel.objects.create(
            name="Test WebChat",
            platform="WebChat",
            active=True,
            config={}
        )

    def test_button_creation_and_storage(self):
        """Test that buttons are properly created and stored in message raw data."""
        # Create test account and chat
        account = Account.objects.create(
            id="webchat_test_user",
            platform="WebChat",
            channel=self.webchat_channel,
            name="Test User",
            raw={"session_key": "test_session"}
        )
        
        chat = Chat.objects.create(
            id="test_chat",
            platform="WebChat",
            channel=self.webchat_channel,
            name="Test Chat"
        )
        
        AccountChat.objects.create(account=account, chat=chat)
        
        # Create message
        message = Message.objects.create(
            id="test_message",
            channel=self.webchat_channel,
            platform="WebChat",
            sender=account,
            chat=chat,
            is_outgoing=False,
            sender_name="Test User",
            text="Test message",
            raw={},
            timestamp=timezone.now(),
            media_type="text"
        )
        
        # Send reply with buttons
        reply = message.reply_with({
            "text": "Choose an option:",
            "buttons": [
                [
                    {"text": "Confirm", "callback_data": {"action": "confirm"}, "type": "callback"},
                    {"text": "Cancel", "callback_data": {"action": "cancel"}, "type": "callback"}
                ]
            ]
        })
        
        # Verify buttons were stored
        assert reply.raw is not None
        assert "interactive_buttons" in reply.raw
        buttons = reply.raw["interactive_buttons"]
        assert len(buttons) == 1  # One row
        assert len(buttons[0]) == 2  # Two buttons
        
        # Verify CallbackExecution records were created
        first_button = buttons[0][0]
        assert "callback_execution_id" in first_button
        
        execution = CallbackExecution.objects.get(id=first_button["callback_execution_id"])
        assert execution.callback_data == {"action": "confirm"}
        assert execution.intended_account == account

    def test_button_security_guest_users(self):
        """Test that only the intended guest session can click buttons."""
        client = Client()
        
        # Create two different sessions
        session1 = SessionStore()
        session1.create()
        session2 = SessionStore()
        session2.create()
        
        # Create account for session1
        account1 = Account.objects.create(
            id=f"webchat_guest_{session1.session_key}",
            platform="WebChat",
            channel=self.webchat_channel,
            name="Guest User",
            raw={"session_key": session1.session_key, "is_guest": True}
        )
        
        chat = Chat.objects.create(
            id="security_test_chat",
            platform="WebChat",
            channel=self.webchat_channel,
            name="Security Test"
        )
        
        AccountChat.objects.create(account=account1, chat=chat)
        
        # Create message with buttons for account1
        message = Message.objects.create(
            id="security_test_message",
            channel=self.webchat_channel,
            platform="WebChat",
            sender=account1,
            chat=chat,
            is_outgoing=True,
            sender_name="Bot",
            text="Security test",
            raw={},
            timestamp=timezone.now(),
            media_type="text"
        )
        
        button_message = message.reply_with({
            "text": "Security test buttons",
            "buttons": [
                [{"text": "Secure Button", "callback_data": {"action": "test"}, "type": "callback"}]
            ]
        })
        
        callback_execution_id = button_message.raw["interactive_buttons"][0][0]["callback_execution_id"]
        
        # Test 1: Legitimate session can click
        client.cookies["sessionid"] = session1.session_key
        response = client.post(
            "/unicom/webchat/button-click/",
            data=json.dumps({"callback_execution_id": callback_execution_id}),
            content_type="application/json"
        )
        assert response.status_code == 200
        
        # Test 2: Different session cannot click
        client.cookies["sessionid"] = session2.session_key
        response = client.post(
            "/unicom/webchat/button-click/",
            data=json.dumps({"callback_execution_id": callback_execution_id}),
            content_type="application/json"
        )
        assert response.status_code == 403

    def test_button_security_authenticated_users(self):
        """Test that only the intended authenticated user can click buttons."""
        # Create two users
        user1 = User.objects.create_user(username="testuser1", password="pass")
        user2 = User.objects.create_user(username="testuser2", password="pass")
        
        client = Client()
        
        # Create account for user1
        account1 = Account.objects.create(
            id=f"webchat_user_{user1.id}",
            platform="WebChat",
            channel=self.webchat_channel,
            name=user1.username,
            raw={"user_id": user1.id}
        )
        
        chat = Chat.objects.create(
            id="auth_security_test",
            platform="WebChat",
            channel=self.webchat_channel,
            name="Auth Security Test"
        )
        
        AccountChat.objects.create(account=account1, chat=chat)
        
        # Create message with buttons for user1
        message = Message.objects.create(
            id="auth_security_message",
            channel=self.webchat_channel,
            platform="WebChat",
            sender=account1,
            chat=chat,
            is_outgoing=True,
            sender_name="Bot",
            text="Auth security test",
            raw={},
            timestamp=timezone.now(),
            media_type="text"
        )
        
        button_message = message.reply_with({
            "text": "Auth security test buttons",
            "buttons": [
                [{"text": "Auth Button", "callback_data": {"action": "auth_test"}, "type": "callback"}]
            ]
        })
        
        callback_execution_id = button_message.raw["interactive_buttons"][0][0]["callback_execution_id"]
        
        # Test 1: Correct user can click
        client.force_login(user1)
        response = client.post(
            "/unicom/webchat/button-click/",
            data=json.dumps({"callback_execution_id": callback_execution_id}),
            content_type="application/json"
        )
        assert response.status_code == 200
        
        # Test 2: Different user cannot click
        client.force_login(user2)
        response = client.post(
            "/unicom/webchat/button-click/",
            data=json.dumps({"callback_execution_id": callback_execution_id}),
            content_type="application/json"
        )
        assert response.status_code == 403

    def test_button_expiration(self):
        """Test that expired buttons are rejected."""
        client = Client()
        
        # Create account and chat
        account = Account.objects.create(
            id="webchat_expire_test",
            platform="WebChat",
            channel=self.webchat_channel,
            name="Test User",
            raw={"session_key": "expire_session"}
        )
        
        chat = Chat.objects.create(
            id="expire_test_chat",
            platform="WebChat",
            channel=self.webchat_channel,
            name="Expire Test"
        )
        
        AccountChat.objects.create(account=account, chat=chat)
        
        # Create expired CallbackExecution
        message = Message.objects.create(
            id="expire_test_message",
            channel=self.webchat_channel,
            platform="WebChat",
            sender=account,
            chat=chat,
            is_outgoing=True,
            sender_name="Bot",
            text="Expire test",
            raw={},
            timestamp=timezone.now(),
            media_type="text"
        )
        
        expired_execution = CallbackExecution.objects.create(
            original_message=message,
            callback_data={"action": "expired"},
            intended_account=account,
            expires_at=timezone.now() - timedelta(seconds=1)  # Expired 1 second ago
        )
        
        # Try to click expired button
        client.cookies["sessionid"] = "expire_session"
        response = client.post(
            "/unicom/webchat/button-click/",
            data=json.dumps({"callback_execution_id": str(expired_execution.id)}),
            content_type="application/json"
        )
        
        assert response.status_code == 403
        assert "expired" in response.json()["error"].lower()

    def test_invalid_button_requests(self):
        """Test various invalid button click scenarios."""
        client = Client()
        
        # Test 1: Missing callback_execution_id
        response = client.post(
            "/unicom/webchat/button-click/",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert response.status_code == 400
        
        # Test 2: Invalid callback_execution_id
        response = client.post(
            "/unicom/webchat/button-click/",
            data=json.dumps({"callback_execution_id": 99999}),
            content_type="application/json"
        )
        assert response.status_code == 404
        
        # Test 3: Malformed JSON
        response = client.post(
            "/unicom/webchat/button-click/",
            data='{"invalid": json}',
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_websocket_message_serialization(self):
        """Test that WebSocket consumer includes button data in message serialization."""
        from unicom.consumers.webchat_consumer import WebChatConsumer
        
        # Create test message with buttons
        account = Account.objects.create(
            id="websocket_test_user",
            platform="WebChat",
            channel=self.webchat_channel,
            name="Test User",
            raw={"session_key": "websocket_session"}
        )
        
        chat = Chat.objects.create(
            id="websocket_test_chat",
            platform="WebChat",
            channel=self.webchat_channel,
            name="WebSocket Test"
        )
        
        message = Message.objects.create(
            id="websocket_test_message",
            channel=self.webchat_channel,
            platform="WebChat",
            sender=account,
            chat=chat,
            is_outgoing=True,
            sender_name="Bot",
            text="WebSocket test with buttons",
            raw={
                "interactive_buttons": [
                    [{"text": "Test Button", "callback_data": {"action": "test"}, "type": "callback"}]
                ]
            },
            timestamp=timezone.now(),
            media_type="text"
        )
        
        # Test message serialization
        consumer = WebChatConsumer()
        serialized = consumer._serialize_message(message)
        
        assert "interactive_buttons" in serialized
        assert serialized["interactive_buttons"] == message.raw["interactive_buttons"]
        assert serialized["text"] == "WebSocket test with buttons"
        assert serialized["id"] == "websocket_test_message"
