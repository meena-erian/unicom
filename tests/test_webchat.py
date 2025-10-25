"""
WebChat functional tests.
Tests WebChat channel, message sending/receiving, and request processing.
"""
import pytest
from django.test import Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction, connections

from unicom.models import (
    Channel,
    Member,
    Request,
    RequestCategory,
    Message,
    Chat,
    Account,
    AccountChat,
)
from unicom.services.webchat.migrate_guest_to_user import migrate_guest_to_user
from tests.utils import wait_for_condition


@pytest.mark.django_db(transaction=True)
class TestWebChatBasics:
    """Test basic WebChat functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test environment."""
        self.client = Client()

        # Create WebChat channel
        with transaction.atomic():
            self.channel = Channel.objects.create(
                name="TestWebChat",
                platform="WebChat",
                config={},
                active=True
            )
            self.channel.refresh_from_db()
            assert self.channel.pk is not None, "Channel was not properly created"

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_channel_creation(self):
        """Test that WebChat channel can be created and validated."""
        assert self.channel.platform == 'WebChat'
        assert self.channel.active is True
        assert self.channel.error is None

    def test_guest_send_message(self):
        """Test guest user sending a message."""
        # Start a session as guest
        session = self.client.session
        session.save()

        # Send message
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Hello from guest user'
        })

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'message' in data
        assert data['message']['text'] == 'Hello from guest user'

        # Verify message was created
        message = Message.objects.get(id=data['message']['id'])
        assert message.text == 'Hello from guest user'
        assert message.is_outgoing is False
        assert message.platform == 'WebChat'

        # Verify account was created for guest
        assert message.sender.id.startswith('webchat_guest_')

        # Verify request was created
        def check_request():
            return Request.objects.filter(message=message).exists()

        wait_for_condition(check_request, timeout=5)

        request = Request.objects.get(message=message)
        assert request.account == message.sender
        assert request.channel == self.channel

        connections.close_all()

    def test_authenticated_send_message(self):
        """Test authenticated user sending a message."""
        # Login
        self.client.login(username='testuser', password='testpass123')

        # Send message
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Hello from authenticated user'
        })

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        # Verify message
        message = Message.objects.get(id=data['message']['id'])
        assert message.text == 'Hello from authenticated user'
        assert message.sender.id == f"webchat_user_{self.user.id}"

        # Verify request was created
        def check_request():
            return Request.objects.filter(message=message).exists()

        wait_for_condition(check_request, timeout=5)

        request = Request.objects.get(message=message)
        assert request.account.id == f"webchat_user_{self.user.id}"

        connections.close_all()

    def test_get_messages(self):
        """Test retrieving messages for a chat."""
        # Login
        self.client.login(username='testuser', password='testpass123')

        # Send first message to create chat
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Message 1'
        })
        data = response.json()
        chat_id = data['chat_id']

        # Send more messages to the same chat
        for i in range(2, 4):
            self.client.post('/unicom/webchat/send/', {
                'text': f'Message {i}',
                'chat_id': chat_id
            })

        # Get messages for this chat
        response = self.client.get(f'/unicom/webchat/messages/?chat_id={chat_id}')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert len(data['messages']) == 3
        assert data['messages'][0]['text'] == 'Message 1'
        assert data['messages'][2]['text'] == 'Message 3'

    def test_list_chats(self):
        """Test listing chats for user."""
        # Login
        self.client.login(username='testuser', password='testpass123')

        # Send a message to create chat
        self.client.post('/unicom/webchat/send/', {
            'text': 'Hello'
        })

        # List chats
        response = self.client.get('/unicom/webchat/chats/')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert len(data['chats']) == 1
        assert data['chats'][0]['platform'] == 'WebChat'
        assert data['chats'][0]['last_message']['text'] == 'Hello'

    def test_bot_reply(self):
        """Test bot replying to user message."""
        # Login
        self.client.login(username='testuser', password='testpass123')

        # Send message
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Hello bot'
        })
        data = response.json()
        chat_id = data['chat_id']

        # Simulate bot reply using channel.send_message
        bot_message = self.channel.send_message({
            'chat_id': chat_id,
            'text': 'Hello user! How can I help you?'
        })

        assert bot_message.is_outgoing is True
        assert bot_message.text == 'Hello user! How can I help you?'

        # Verify user can see bot message
        response = self.client.get(f'/unicom/webchat/messages/?chat_id={chat_id}')
        data = response.json()
        messages = data['messages']

        # Should have both user and bot messages
        assert len(messages) == 2
        assert messages[0]['text'] == 'Hello bot'
        assert messages[0]['is_outgoing'] is False
        assert messages[1]['text'] == 'Hello user! How can I help you?'
        assert messages[1]['is_outgoing'] is True

    def test_multiple_separate_chats(self):
        """Test that users can create multiple separate chats."""
        # Login
        self.client.login(username='testuser', password='testpass123')

        # Create first chat
        response1 = self.client.post('/unicom/webchat/send/', {
            'text': 'First chat message 1'
        })
        data1 = response1.json()
        chat_id_1 = data1['chat_id']

        # Send another message to first chat
        self.client.post('/unicom/webchat/send/', {
            'text': 'First chat message 2',
            'chat_id': chat_id_1
        })

        # Create second chat (by not providing chat_id)
        response2 = self.client.post('/unicom/webchat/send/', {
            'text': 'Second chat message 1'
        })
        data2 = response2.json()
        chat_id_2 = data2['chat_id']

        # Send another message to second chat
        self.client.post('/unicom/webchat/send/', {
            'text': 'Second chat message 2',
            'chat_id': chat_id_2
        })

        # Verify chat IDs are different
        assert chat_id_1 != chat_id_2

        # Verify first chat has only first chat messages
        response = self.client.get(f'/unicom/webchat/messages/?chat_id={chat_id_1}')
        data = response.json()
        assert len(data['messages']) == 2
        assert data['messages'][0]['text'] == 'First chat message 1'
        assert data['messages'][1]['text'] == 'First chat message 2'

        # Verify second chat has only second chat messages
        response = self.client.get(f'/unicom/webchat/messages/?chat_id={chat_id_2}')
        data = response.json()
        assert len(data['messages']) == 2
        assert data['messages'][0]['text'] == 'Second chat message 1'
        assert data['messages'][1]['text'] == 'Second chat message 2'

        # Verify user can see both chats in chat list
        response = self.client.get('/unicom/webchat/chats/')
        data = response.json()
        assert len(data['chats']) == 2

        # Verify both chats are accessible
        chat_ids = {chat['id'] for chat in data['chats']}
        assert chat_id_1 in chat_ids
        assert chat_id_2 in chat_ids


@pytest.mark.django_db(transaction=True)
class TestWebChatRequestProcessing:
    """Test WebChat request categorization and processing."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test environment."""
        self.client = Client()

        # Create WebChat channel
        with transaction.atomic():
            self.channel = Channel.objects.create(
                name="TestWebChat",
                platform="WebChat",
                config={},
                active=True
            )

        # Create test user and member
        self.user = User.objects.create_user(
            username='testuser',
            email='member@example.com',
            password='testpass123'
        )

        self.member = Member.objects.create(
            name="Test Member",
            email='member@example.com',
            user=self.user
        )

    def _wait_request(self, *, cond, timeout=5):
        """Wait for a request matching the condition."""
        def check_condition():
            try:
                return Request.objects.filter(**cond).exists()
            except Exception as e:
                print(f"Error in check_condition: {e}")
                return False

        return wait_for_condition(check_condition, timeout=timeout)

    def test_request_creation_no_categories(self):
        """Test request creation when there are no categories."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Test message'
        })

        assert response.status_code == 200
        data = response.json()
        message_id = data['message']['id']

        # Wait for request
        self._wait_request(cond={'message_id': message_id, 'status': 'QUEUED'})

        request = Request.objects.get(message_id=message_id)
        assert request.member == self.member
        assert request.status == 'QUEUED'
        assert request.category is None

        connections.close_all()

    def test_request_with_public_category(self):
        """Test request processing with a public category."""
        # Create public category
        public_cat = RequestCategory.objects.create(
            name="Public Support",
            sequence=1,
            is_public=True,
            processing_function="""
def process(request, metadata):
    return {'category_match': True}
"""
        )

        self.client.login(username='testuser', password='testpass123')

        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Test public category'
        })

        data = response.json()
        message_id = data['message']['id']

        # Wait for request to be categorized
        self._wait_request(cond={'message_id': message_id, 'status': 'QUEUED'})

        request = Request.objects.get(message_id=message_id)
        assert request.member == self.member
        assert request.status == 'QUEUED'
        assert request.category == public_cat

        connections.close_all()

    def test_request_with_member_only_category(self):
        """Test request processing with a member-only category."""
        # Create member-only category
        member_cat = RequestCategory.objects.create(
            name="Member Support",
            sequence=1,
            is_public=False,
            processing_function="""
def process(request, metadata):
    return {'category_match': True}
"""
        )
        member_cat.authorized_members.add(self.member)

        self.client.login(username='testuser', password='testpass123')

        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Test member category'
        })

        data = response.json()
        message_id = data['message']['id']

        # Wait for request
        self._wait_request(cond={'message_id': message_id, 'status': 'QUEUED'})

        request = Request.objects.get(message_id=message_id)
        assert request.member == self.member
        assert request.category == member_cat

        connections.close_all()


@pytest.mark.django_db(transaction=True)
class TestWebChatGuestMigration:
    """Test guest-to-user migration."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test environment."""
        self.client = Client()

        # Create WebChat channel
        with transaction.atomic():
            self.channel = Channel.objects.create(
                name="TestWebChat",
                platform="WebChat",
                config={},
                active=True
            )

    def test_guest_to_user_migration(self):
        """Test migrating guest chat to authenticated user."""
        # Send message as guest
        session = self.client.session
        session.save()
        session_key = session.session_key

        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Message from guest'
        })

        assert response.status_code == 200
        data = response.json()
        guest_account_id = f"webchat_guest_{session_key}"

        # Verify guest account exists
        guest_account = Account.objects.get(id=guest_account_id)
        assert guest_account is not None

        # Verify message was created
        message = Message.objects.get(id=data['message']['id'])
        assert message.sender == guest_account

        # Create user and migrate
        user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='pass123'
        )

        # Migrate guest data
        user_account = migrate_guest_to_user(session_key, user)

        assert user_account.id == f"webchat_user_{user.id}"

        # Verify guest account is deleted
        with pytest.raises(Account.DoesNotExist):
            Account.objects.get(id=guest_account_id)

        # Verify message was transferred
        message.refresh_from_db()
        assert message.sender == user_account

        # Verify chat was transferred
        chat = Chat.objects.get(messages=message)
        account_chats = AccountChat.objects.filter(chat=chat, account=user_account)
        assert account_chats.exists()

    def test_guest_messages_preserved_after_login(self):
        """Test that guest messages are preserved when user logs in."""
        # Send messages as guest
        session = self.client.session
        session.save()
        session_key = session.session_key

        guest_account_id = f"webchat_guest_{session_key}"

        # Send first message to create chat
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Guest message 1'
        })
        data = response.json()
        chat_id = data['chat_id']

        # Send more messages to same chat
        for i in range(2, 4):
            self.client.post('/unicom/webchat/send/', {
                'text': f'Guest message {i}',
                'chat_id': chat_id
            })

        # Create and login user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='pass123'
        )

        # Migrate
        migrate_guest_to_user(session_key, user)

        # Login
        self.client.login(username='testuser', password='pass123')

        # User should be able to access the chat because AccountChat was updated
        response = self.client.get(f'/unicom/webchat/messages/?chat_id={chat_id}')
        data = response.json()

        assert len(data['messages']) == 3
        assert data['messages'][0]['text'] == 'Guest message 1'
        assert data['messages'][2]['text'] == 'Guest message 3'


@pytest.mark.django_db(transaction=True)
class TestWebChatSecurity:
    """Test WebChat security features."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test environment."""
        self.client = Client()

        # Create WebChat channel
        with transaction.atomic():
            self.channel = Channel.objects.create(
                name="TestWebChat",
                platform="WebChat",
                config={},
                active=True
            )

        # Create two users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )

        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )

    def test_users_cannot_see_each_others_chats(self):
        """Test that users can only see their own chats."""
        # User1 sends message
        self.client.login(username='user1', password='pass123')
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'User1 message'
        })
        user1_chat_id = response.json()['message']['chat_id']
        self.client.logout()

        # User2 sends message
        self.client.login(username='user2', password='pass123')
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'User2 message'
        })
        user2_chat_id = response.json()['message']['chat_id']

        # User2 lists chats - should only see their own
        response = self.client.get('/unicom/webchat/chats/')
        data = response.json()
        assert len(data['chats']) == 1
        assert data['chats'][0]['id'] == user2_chat_id

        # User2 tries to access User1's messages - should fail or be empty
        response = self.client.get(f'/unicom/webchat/messages/?chat_id={user1_chat_id}')
        assert response.status_code == 404  # Chat not found / access denied

    def test_blocked_account_cannot_send(self):
        """Test that blocked accounts cannot send messages."""
        # Login and send message
        self.client.login(username='user1', password='pass123')
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Test message'
        })
        assert response.status_code == 200

        # Block the account
        account = Account.objects.get(id=f"webchat_user_{self.user1.id}")
        account.blocked = True
        account.save()

        # Try to send another message
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Blocked message'
        })
        assert response.status_code == 403
        data = response.json()
        assert 'blocked' in data['error'].lower()

    def test_guest_cannot_delete_chat(self):
        """Ensure guest users cannot delete chats."""
        response = self.client.post('/unicom/webchat/send/', {'text': 'Guest message'})
        assert response.status_code == 200
        chat_id = response.json()['message']['chat_id']

        delete_response = self.client.delete(f'/unicom/webchat/chat/{chat_id}/delete/')
        assert delete_response.status_code == 401
        chat = Chat.objects.get(id=chat_id)
        assert chat.is_archived is False

    def test_user_can_delete_own_chat(self):
        """Ensure authenticated users can delete their own chats."""
        self.client.login(username='user1', password='pass123')
        response = self.client.post('/unicom/webchat/send/', {'text': 'User1 message'})
        assert response.status_code == 200
        chat_id = response.json()['message']['chat_id']

        delete_response = self.client.delete(f'/unicom/webchat/chat/{chat_id}/delete/')
        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data['success'] is True
        assert 'message' in data

        chat = Chat.objects.get(id=chat_id)
        assert chat.is_archived is True

    def test_user_cannot_delete_other_users_chat(self):
        """Ensure users cannot delete chats they do not own."""
        self.client.login(username='user1', password='pass123')
        response = self.client.post('/unicom/webchat/send/', {'text': 'User1 message'})
        assert response.status_code == 200
        user1_chat_id = response.json()['message']['chat_id']
        self.client.logout()

        self.client.login(username='user2', password='pass123')
        delete_response = self.client.delete(f'/unicom/webchat/chat/{user1_chat_id}/delete/')
        assert delete_response.status_code == 404

        chat = Chat.objects.get(id=user1_chat_id)
        assert chat.is_archived is False


@pytest.mark.django_db(transaction=True)
class TestWebChatCustomFiltration:
    """Test custom filtration features (project-based chats, metadata filtering)."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test environment."""
        self.client = Client()

        # Create WebChat channel
        with transaction.atomic():
            self.channel = Channel.objects.create(
                name="TestWebChat",
                platform="WebChat",
                config={},
                active=True
            )

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_chat_with_metadata(self):
        """Test creating a chat with custom metadata."""
        self.client.login(username='testuser', password='testpass123')

        # Send message with metadata (creates new chat)
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Hello from project 123',
            'metadata': '{"project_id": 123, "department": "engineering"}'
        })
        assert response.status_code == 200
        data = response.json()
        chat_id = data['chat_id']

        # Verify chat has metadata
        chat = Chat.objects.get(id=chat_id)
        assert chat.metadata['project_id'] == 123
        assert chat.metadata['department'] == 'engineering'

    def test_filter_chats_by_metadata_project_id(self):
        """Test filtering chats by project_id."""
        self.client.login(username='testuser', password='testpass123')

        # Create chat for project 123
        response1 = self.client.post('/unicom/webchat/send/', {
            'text': 'Project 123 chat',
            'metadata': '{"project_id": 123}'
        })
        chat_id_123 = response1.json()['chat_id']

        # Create chat for project 456
        response2 = self.client.post('/unicom/webchat/send/', {
            'text': 'Project 456 chat',
            'metadata': '{"project_id": 456}'
        })
        chat_id_456 = response2.json()['chat_id']

        # Create chat with no metadata
        response3 = self.client.post('/unicom/webchat/send/', {
            'text': 'No project chat'
        })
        chat_id_no_project = response3.json()['chat_id']

        # Filter by project 123
        response = self.client.get('/unicom/webchat/chats/?metadata__project_id=123')
        assert response.status_code == 200
        data = response.json()
        chat_ids = [chat['id'] for chat in data['chats']]

        assert chat_id_123 in chat_ids
        assert chat_id_456 not in chat_ids
        assert chat_id_no_project not in chat_ids

    def test_filter_chats_by_multiple_metadata_fields(self):
        """Test filtering chats by multiple metadata fields."""
        self.client.login(username='testuser', password='testpass123')

        # Create chat with project_id and department
        response1 = self.client.post('/unicom/webchat/send/', {
            'text': 'Engineering project 123',
            'metadata': '{"project_id": 123, "department": "engineering"}'
        })
        chat_id_eng_123 = response1.json()['chat_id']

        # Create chat with same project_id but different department
        response2 = self.client.post('/unicom/webchat/send/', {
            'text': 'Sales project 123',
            'metadata': '{"project_id": 123, "department": "sales"}'
        })
        chat_id_sales_123 = response2.json()['chat_id']

        # Create chat with different project_id and same department
        response3 = self.client.post('/unicom/webchat/send/', {
            'text': 'Engineering project 456',
            'metadata': '{"project_id": 456, "department": "engineering"}'
        })
        chat_id_eng_456 = response3.json()['chat_id']

        # Filter by project_id=123 AND department=engineering
        response = self.client.get(
            '/unicom/webchat/chats/?metadata__project_id=123&metadata__department=engineering'
        )
        assert response.status_code == 200
        data = response.json()
        chat_ids = [chat['id'] for chat in data['chats']]

        assert chat_id_eng_123 in chat_ids
        assert chat_id_sales_123 not in chat_ids
        assert chat_id_eng_456 not in chat_ids

    def test_filter_chats_by_metadata_with_comparison_operators(self):
        """Test filtering with comparison operators (gte, lte, etc.)."""
        self.client.login(username='testuser', password='testpass123')

        # Create chats with different priority levels
        priorities = [3, 7, 9]
        chat_ids = {}

        for priority in priorities:
            response = self.client.post('/unicom/webchat/send/', {
                'text': f'Priority {priority} chat',
                'metadata': f'{{"priority": {priority}}}'
            })
            chat_ids[priority] = response.json()['chat_id']

        # Filter by priority >= 7
        response = self.client.get('/unicom/webchat/chats/?metadata__priority__gte=7')
        assert response.status_code == 200
        data = response.json()
        filtered_ids = [chat['id'] for chat in data['chats']]

        assert chat_ids[3] not in filtered_ids
        assert chat_ids[7] in filtered_ids
        assert chat_ids[9] in filtered_ids

    def test_filter_chats_combine_metadata_and_standard_fields(self):
        """Test combining metadata filters with standard Chat model filters."""
        self.client.login(username='testuser', password='testpass123')

        # Create active chat for project 123
        response1 = self.client.post('/unicom/webchat/send/', {
            'text': 'Active project 123',
            'metadata': '{"project_id": 123}'
        })
        active_chat_id = response1.json()['chat_id']

        # Create archived chat for project 123
        response2 = self.client.post('/unicom/webchat/send/', {
            'text': 'Archived project 123',
            'metadata': '{"project_id": 123}'
        })
        archived_chat_id = response2.json()['chat_id']

        # Archive the second chat
        archived_chat = Chat.objects.get(id=archived_chat_id)
        archived_chat.is_archived = True
        archived_chat.save()

        # Filter by project_id=123 AND is_archived=false
        response = self.client.get(
            '/unicom/webchat/chats/?metadata__project_id=123&is_archived=false'
        )
        assert response.status_code == 200
        data = response.json()
        chat_ids = [chat['id'] for chat in data['chats']]

        assert active_chat_id in chat_ids
        assert archived_chat_id not in chat_ids

    def test_metadata_included_in_chat_list_response(self):
        """Test that metadata is included in chat list API response."""
        self.client.login(username='testuser', password='testpass123')

        # Create chat with metadata
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Chat with metadata',
            'metadata': '{"project_id": 123, "tags": ["urgent", "bug"]}'
        })
        chat_id = response.json()['chat_id']

        # Get chat list
        response = self.client.get('/unicom/webchat/chats/')
        assert response.status_code == 200
        data = response.json()

        # Find our chat in the list
        our_chat = next((c for c in data['chats'] if c['id'] == chat_id), None)
        assert our_chat is not None
        assert 'metadata' in our_chat
        assert our_chat['metadata']['project_id'] == 123
        assert our_chat['metadata']['tags'] == ['urgent', 'bug']

    def test_metadata_supports_nested_objects(self):
        """Test that metadata supports nested objects."""
        self.client.login(username='testuser', password='testpass123')

        # Create chat with nested metadata
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Chat with nested metadata',
            'metadata': '''{
                "project": {
                    "id": 123,
                    "name": "Project Alpha"
                },
                "assigned_to": {
                    "user_id": 456,
                    "name": "John Doe"
                }
            }'''
        })
        chat_id = response.json()['chat_id']

        # Verify nested metadata is stored correctly
        chat = Chat.objects.get(id=chat_id)
        assert chat.metadata['project']['id'] == 123
        assert chat.metadata['project']['name'] == 'Project Alpha'
        assert chat.metadata['assigned_to']['user_id'] == 456

    def test_empty_metadata_for_chats_without_metadata(self):
        """Test that chats without metadata have empty dict."""
        self.client.login(username='testuser', password='testpass123')

        # Create chat without metadata
        response = self.client.post('/unicom/webchat/send/', {
            'text': 'Chat without metadata'
        })
        chat_id = response.json()['chat_id']

        # Verify metadata is empty dict
        chat = Chat.objects.get(id=chat_id)
        assert chat.metadata == {}

        # Verify metadata is in response
        response = self.client.get('/unicom/webchat/chats/')
        data = response.json()
        our_chat = next((c for c in data['chats'] if c['id'] == chat_id), None)
        assert our_chat['metadata'] == {}
