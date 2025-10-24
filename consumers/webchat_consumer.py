"""
WebChat WebSocket Consumer (Optional - requires Django Channels)

This consumer provides real-time updates for WebChat when Django Channels is installed.
If Channels is not available, the application will fall back to polling-based updates.

Installation:
    pip install channels channels-redis

Configuration in settings.py:
    INSTALLED_APPS = [
        ...
        'channels',
    ]

    ASGI_APPLICATION = 'your_project.asgi.application'

    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [('127.0.0.1', 6379)],
            },
        },
    }

Routing in asgi.py or routing.py:
    from django.urls import path
    from unicom.consumers.webchat_consumer import WebChatConsumer

    websocket_urlpatterns = [
        path('ws/unicom/webchat/', WebChatConsumer.as_asgi()),
    ]
"""

try:
    from channels.generic.websocket import AsyncJsonWebsocketConsumer
    from channels.db import database_sync_to_async
    from django.apps import apps
    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False
    # Create a dummy base class so the file doesn't fail to import
    class AsyncJsonWebsocketConsumer:
        pass


class WebChatConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time WebChat updates.

    Supports:
    - Real-time message delivery
    - Chat list updates
    - Custom filtration (e.g., by project_id, department, etc.)
    - Typing indicators (future)
    - Read receipts (future)

    Client-to-Server Messages:
    {
        "action": "subscribe",
        "filters": {
            "metadata__project_id": 123,
            "is_archived": false
        }
    }

    {
        "action": "send_message",
        "chat_id": "webchat_abc123",
        "text": "Hello",
        "metadata": {"project_id": 123}  // For new chat creation
    }

    {
        "action": "get_chats",
        "filters": {"metadata__project_id": 123}
    }

    {
        "action": "get_messages",
        "chat_id": "webchat_abc123",
        "limit": 50
    }

    Server-to-Client Messages:
    {
        "type": "new_message",
        "message": {...},
        "chat_id": "webchat_abc123"
    }

    {
        "type": "chat_update",
        "chat": {...}
    }

    {
        "type": "chats_list",
        "chats": [...]
    }
    """

    def __init__(self, *args, **kwargs):
        if not CHANNELS_AVAILABLE:
            raise ImportError(
                "Django Channels is not installed. Please install it with: "
                "pip install channels channels-redis"
            )
        super().__init__(*args, **kwargs)
        self.account = None
        self.account_id = None
        self.filters = {}
        self.subscribed_chats = set()

    async def connect(self):
        """Handle WebSocket connection."""
        # Accept connection
        await self.accept()

        # Get or create account
        self.account = await self.get_or_create_account()
        self.account_id = self.account.id

        # Add to account's personal group
        await self.channel_layer.group_add(
            f"webchat_account_{self.account_id}",
            self.channel_name
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Remove from account's personal group
        if self.account_id:
            await self.channel_layer.group_discard(
                f"webchat_account_{self.account_id}",
                self.channel_name
            )

        # Remove from all subscribed chat groups
        for chat_id in self.subscribed_chats:
            await self.channel_layer.group_discard(
                f"webchat_chat_{chat_id}",
                self.channel_name
            )

    async def receive_json(self, content):
        """Handle incoming WebSocket messages."""
        action = content.get('action')

        if action == 'subscribe':
            # Subscribe to filtered chats
            filters = content.get('filters', {})
            self.filters = filters
            await self.send_filtered_chats()

        elif action == 'send_message':
            # Send a message
            chat_id = content.get('chat_id')
            text = content.get('text')
            metadata = content.get('metadata', {})

            message = await self.save_message(chat_id, text, metadata)
            if message:
                await self.send_json({
                    'type': 'message_sent',
                    'success': True,
                    'message': await self.serialize_message(message),
                    'chat_id': message.chat_id
                })

                # Broadcast to chat participants
                await self.channel_layer.group_send(
                    f"webchat_chat_{message.chat_id}",
                    {
                        'type': 'new_message',
                        'message': await self.serialize_message(message),
                        'chat_id': message.chat_id
                    }
                )

        elif action == 'get_chats':
            # Get list of chats
            filters = content.get('filters', self.filters)
            chats = await self.get_chats(filters)
            await self.send_json({
                'type': 'chats_list',
                'chats': chats
            })

        elif action == 'get_messages':
            # Get messages for a chat
            chat_id = content.get('chat_id')
            limit = content.get('limit', 50)
            messages = await self.get_messages(chat_id, limit)
            await self.send_json({
                'type': 'messages_list',
                'chat_id': chat_id,
                'messages': messages
            })

        elif action == 'subscribe_chat':
            # Subscribe to a specific chat for real-time updates
            chat_id = content.get('chat_id')
            if chat_id and await self.has_chat_access(chat_id):
                await self.channel_layer.group_add(
                    f"webchat_chat_{chat_id}",
                    self.channel_name
                )
                self.subscribed_chats.add(chat_id)

        elif action == 'unsubscribe_chat':
            # Unsubscribe from a specific chat
            chat_id = content.get('chat_id')
            if chat_id in self.subscribed_chats:
                await self.channel_layer.group_discard(
                    f"webchat_chat_{chat_id}",
                    self.channel_name
                )
                self.subscribed_chats.remove(chat_id)

    async def new_message(self, event):
        """
        Handler for new_message events from channel layer.
        Sends the message to the WebSocket client.
        """
        await self.send_json({
            'type': 'new_message',
            'message': event['message'],
            'chat_id': event['chat_id']
        })

    async def chat_update(self, event):
        """
        Handler for chat_update events from channel layer.
        Sends the chat update to the WebSocket client.
        """
        await self.send_json({
            'type': 'chat_update',
            'chat': event['chat']
        })

    # Database operations

    @database_sync_to_async
    def get_or_create_account(self):
        """Get or create WebChat account for current user/session."""
        from unicom.services.webchat.get_or_create_account import get_or_create_account
        from unicom.models import Channel

        # Get WebChat channel
        channel = Channel.objects.filter(platform='WebChat', active=True).first()
        if not channel:
            raise ValueError("No active WebChat channel found")

        # Use the scope to get user and session
        account = get_or_create_account(channel, self.scope)
        return account

    @database_sync_to_async
    def has_chat_access(self, chat_id):
        """Check if account has access to a chat."""
        from unicom.models import Chat, AccountChat

        try:
            chat = Chat.objects.get(id=chat_id, platform='WebChat')
            return AccountChat.objects.filter(account=self.account, chat=chat).exists()
        except Chat.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, chat_id, text, metadata):
        """Save a message to the database."""
        from unicom.services.webchat.save_webchat_message import save_webchat_message
        from unicom.models import Channel

        channel = Channel.objects.filter(platform='WebChat', active=True).first()
        if not channel:
            return None

        message_data = {
            'text': text,
            'chat_id': chat_id,
            'media_type': 'text',
            'metadata': metadata
        }

        # Create a mock request object with session and user
        class MockRequest:
            def __init__(self, scope):
                self.scope = scope
                self.user = scope.get('user')
                self.session = scope.get('session', {})

        request = MockRequest(self.scope)
        message = save_webchat_message(channel, message_data, request)
        return message

    @database_sync_to_async
    def get_chats(self, filters):
        """Get filtered list of chats."""
        from unicom.models import Chat

        # Get chats for this account
        chats = Chat.objects.filter(
            platform='WebChat',
            accountchat__account=self.account
        )

        # Apply filters
        filter_params = {}
        for key, value in filters.items():
            if key.startswith('metadata__'):
                # Convert values
                if isinstance(value, str):
                    if value.lower() in ['true', 'false']:
                        value = value.lower() == 'true'
                    elif value.isdigit():
                        value = int(value)
                filter_params[key] = value
            elif hasattr(Chat, key.split('__')[0]):
                if isinstance(value, str) and value.lower() in ['true', 'false']:
                    value = value.lower() == 'true'
                filter_params[key] = value

        if filter_params:
            chats = chats.filter(**filter_params)

        # Order by most recent
        chats = chats.order_by('-last_message__timestamp')

        # Serialize
        return [self._serialize_chat_sync(chat) for chat in chats]

    @database_sync_to_async
    def get_messages(self, chat_id, limit):
        """Get messages for a chat."""
        from unicom.models import Message, Chat, AccountChat

        # Verify access
        try:
            chat = Chat.objects.get(id=chat_id, platform='WebChat')
            AccountChat.objects.get(account=self.account, chat=chat)
        except (Chat.DoesNotExist, AccountChat.DoesNotExist):
            return []

        # Get messages
        messages = Message.objects.filter(chat=chat).order_by('-timestamp')[:limit]
        messages = list(reversed(messages))

        return [self._serialize_message_sync(msg) for msg in messages]

    @database_sync_to_async
    def serialize_message(self, message):
        """Serialize a message to JSON (async wrapper)."""
        return self._serialize_message_sync(message)

    def _serialize_message_sync(self, message):
        """Serialize a message to JSON (sync)."""
        return {
            'id': message.id,
            'text': message.text,
            'html': message.html,
            'is_outgoing': message.is_outgoing,
            'sender_name': message.sender_name,
            'timestamp': message.timestamp.isoformat(),
            'media_type': message.media_type,
            'media_url': message.media.url if message.media else None,
        }

    def _serialize_chat_sync(self, chat):
        """Serialize a chat to JSON (sync)."""
        last_msg = chat.last_message
        return {
            'id': chat.id,
            'name': chat.name,
            'platform': chat.platform,
            'channel_id': chat.channel_id,
            'is_archived': chat.is_archived,
            'metadata': chat.metadata,
            'last_message': {
                'text': last_msg.text if last_msg else None,
                'timestamp': last_msg.timestamp.isoformat() if last_msg else None,
            } if last_msg else None
        }

    async def send_filtered_chats(self):
        """Send filtered chats to client."""
        chats = await self.get_chats(self.filters)
        await self.send_json({
            'type': 'chats_list',
            'chats': chats
        })


# Helper function to broadcast messages to chat participants
async def broadcast_message_to_chat(chat_id, message):
    """
    Broadcast a new message to all participants of a chat.
    Call this from your message save logic when Channels is available.
    """
    from channels.layers import get_channel_layer

    if not CHANNELS_AVAILABLE:
        return

    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    # Serialize message
    consumer = WebChatConsumer()
    message_data = consumer._serialize_message_sync(message)

    # Send to chat group
    await channel_layer.group_send(
        f"webchat_chat_{chat_id}",
        {
            'type': 'new_message',
            'message': message_data,
            'chat_id': chat_id
        }
    )


# Helper function to check if Channels is available
def is_channels_available():
    """Check if Django Channels is installed and configured."""
    return CHANNELS_AVAILABLE
