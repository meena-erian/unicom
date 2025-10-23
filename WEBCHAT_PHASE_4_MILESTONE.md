# WebChat Implementation - Phase 4: Real-time Updates

**Goal**: Add real-time message delivery and notifications without page refresh, using either WebSockets (Django Channels) or Long Polling as a fallback.

**Prerequisites**: Phases 1, 2, & 3 must be complete (backend, UI, multi-chat all functional)

---

## 1. Architecture Decision: WebSockets vs Long Polling

### 1.1 WebSocket Approach (Recommended)
**Pros**:
- True real-time bidirectional communication
- Lower latency
- More efficient (persistent connection)
- Better for scaling

**Cons**:
- Requires Django Channels
- More complex setup
- Needs Redis/channel layer

### 1.2 Long Polling Approach (Fallback)
**Pros**:
- No additional dependencies
- Works with standard Django
- Simpler to implement

**Cons**:
- Higher server load
- Higher latency
- Less efficient

**Recommendation**: Implement both, with WebSocket as primary and long polling as fallback

---

## 2. WebSocket Implementation (Primary)

### 2.1 Install Django Channels
**Dependencies**:
```bash
pip install channels channels-redis daphne
```

**Update settings.py**:
```python
INSTALLED_APPS = [
    # ...
    'daphne',  # Must be at top
    'channels',
    'unicom',
    # ...
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
```

### 2.2 ASGI Configuration
**File**: `your_project/asgi.py`

```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

django_asgi_app = get_asgi_application()

from unicom.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
```

### 2.3 WebSocket Routing
**File**: `unicom/routing.py`

```python
from django.urls import path
from unicom.consumers import WebChatConsumer

websocket_urlpatterns = [
    path('ws/webchat/', WebChatConsumer.as_asgi()),
]
```

### 2.4 WebSocket Consumer
**File**: `unicom/consumers.py`

```python
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from unicom.models import Account, Chat, Message
from unicom.services.webchat.get_or_create_account import get_or_create_account


class WebChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Handle WebSocket connection.
        Add user to their personal notification channel.
        """
        # Get user from session (works for both auth and guest users)
        self.user = self.scope['user']
        self.session = self.scope.get('session', {})

        # Get or create account
        self.account = await self._get_account()

        if not self.account:
            await self.close()
            return

        # Subscribe to account's notification channel
        self.account_group = f"webchat_account_{self.account.id}"
        await self.channel_layer.group_add(
            self.account_group,
            self.channel_name
        )

        await self.accept()

        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'account_id': self.account.id
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'account_group'):
            await self.channel_layer.group_discard(
                self.account_group,
                self.channel_name
            )

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages.
        Currently just for ping/pong keepalive.
        Actual message sending still goes through HTTP API.
        """
        data = json.loads(text_data)
        msg_type = data.get('type')

        if msg_type == 'ping':
            await self.send(text_data=json.dumps({
                'type': 'pong',
                'timestamp': data.get('timestamp')
            }))

    async def chat_message(self, event):
        """
        Handle message broadcast from channel layer.
        Called when new message is sent to a chat this user is in.
        """
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message'],
            'chat_id': event['chat_id']
        }))

    async def typing_indicator(self, event):
        """Handle typing indicator broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'chat_id': event['chat_id'],
            'is_typing': event['is_typing'],
            'user_name': event['user_name']
        }))

    @database_sync_to_async
    def _get_account(self):
        """Get or create account for connected user."""
        # Create a mock request object for get_or_create_account
        class MockRequest:
            def __init__(self, user, session):
                self.user = user
                self.session = session

        mock_request = MockRequest(self.user, self.session)

        try:
            # Get default WebChat channel
            from unicom.models import Channel
            channel = Channel.objects.filter(platform='WebChat', active=True).first()
            if not channel:
                return None

            return get_or_create_account(channel, mock_request)
        except Exception as e:
            print(f"Error getting account: {e}")
            return None
```

### 2.5 Broadcast New Messages
**File**: `unicom/services/webchat/save_webchat_message.py`

**Update to broadcast via WebSocket**:
```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def save_webchat_message(channel, message_data, request, user=None):
    # ... existing message saving logic ...

    # After message is saved, broadcast to WebSocket subscribers
    if message.is_outgoing:
        # Broadcast to all chat participants
        _broadcast_message_to_chat(message)

    return message


def _broadcast_message_to_chat(message):
    """
    Broadcast message to all accounts in the chat via WebSocket.
    """
    channel_layer = get_channel_layer()

    # Get all accounts in this chat
    from unicom.models import AccountChat
    accounts = AccountChat.objects.filter(chat=message.chat).values_list('account_id', flat=True)

    # Serialize message
    message_data = {
        'id': message.id,
        'text': message.text,
        'is_outgoing': message.is_outgoing,
        'sender_name': message.sender_name,
        'timestamp': message.timestamp.isoformat(),
        'media_type': message.media_type,
        'media_url': message.media.url if message.media else None,
    }

    # Broadcast to each account's group
    for account_id in accounts:
        group_name = f"webchat_account_{account_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'chat_message',
                'chat_id': message.chat_id,
                'message': message_data
            }
        )
```

---

## 3. Long Polling Implementation (Fallback)

### 3.1 Long Polling Endpoint
**File**: `unicom/views/webchat_views.py`

```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import time
import asyncio


@require_http_methods(["GET"])
def poll_messages_api(request):
    """
    Long polling endpoint for new messages.
    Waits up to 30 seconds for new messages before returning.
    """
    chat_id = request.GET.get('chat_id')
    last_message_id = request.GET.get('last_message_id')
    timeout = int(request.GET.get('timeout', 30))  # seconds

    if not chat_id:
        return JsonResponse({'error': 'chat_id required'}, status=400)

    # Get account
    from unicom.services.webchat.get_or_create_account import get_or_create_account
    from unicom.models import Channel

    channel = Channel.objects.filter(platform='WebChat', active=True).first()
    if not channel:
        return JsonResponse({'error': 'No WebChat channel found'}, status=500)

    account = get_or_create_account(channel, request)

    # Verify user has access to this chat
    from unicom.models import Chat, AccountChat
    try:
        chat = Chat.objects.get(id=chat_id)
        AccountChat.objects.get(account=account, chat=chat)
    except (Chat.DoesNotExist, AccountChat.DoesNotExist):
        return JsonResponse({'error': 'Chat not found'}, status=404)

    # Poll for new messages
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check for new messages
        from unicom.models import Message

        query = Message.objects.filter(chat=chat).order_by('-timestamp')

        if last_message_id:
            # Get messages newer than last_message_id
            try:
                last_msg = Message.objects.get(id=last_message_id)
                query = query.filter(timestamp__gt=last_msg.timestamp)
            except Message.DoesNotExist:
                pass

        new_messages = list(query[:10])

        if new_messages:
            # New messages found, return them
            messages_data = [{
                'id': msg.id,
                'text': msg.text,
                'is_outgoing': msg.is_outgoing,
                'sender_name': msg.sender_name,
                'timestamp': msg.timestamp.isoformat(),
                'media_type': msg.media_type,
                'media_url': msg.media.url if msg.media else None,
            } for msg in new_messages]

            return JsonResponse({
                'success': True,
                'messages': messages_data,
                'has_more': False
            })

        # No new messages yet, wait a bit and check again
        time.sleep(1)

    # Timeout reached, return empty
    return JsonResponse({
        'success': True,
        'messages': [],
        'has_more': False
    })
```

**Add to urls.py**:
```python
path('webchat/poll/', poll_messages_api, name='webchat_poll'),
```

---

## 4. Frontend WebSocket Integration

### 4.1 WebSocket Client
**File**: `unicom/static/unicom/webchat/utils/websocket-client.js`

```javascript
export class WebSocketClient {
  constructor(url, onMessage, onError) {
    this.url = url;
    this.onMessage = onMessage;
    this.onError = onError;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // ms
  }

  connect() {
    // Determine WebSocket URL (ws:// or wss://)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${this.url}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.onMessage(data);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.onError?.(error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket closed');
      this._attemptReconnect();
    };
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  _attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

      console.log(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts})`);

      setTimeout(() => {
        this.connect();
      }, delay);
    } else {
      console.error('Max reconnect attempts reached');
      this.onError?.(new Error('WebSocket connection failed'));
    }
  }

  // Ping to keep connection alive
  startPing(interval = 30000) {
    this.pingInterval = setInterval(() => {
      this.send({ type: 'ping', timestamp: Date.now() });
    }, interval);
  }

  stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}
```

### 4.2 Update Main Component
**File**: `unicom/static/unicom/webchat/webchat-component.js`

```javascript
import { WebSocketClient } from './utils/websocket-client.js';

export class UnicomChat extends LitElement {
  static properties = {
    // ... existing properties ...
    useWebSocket: { type: Boolean, attribute: 'use-websocket' },
    wsConnected: { type: Boolean, state: true },
  };

  constructor() {
    super();
    // ... existing code ...
    this.useWebSocket = true; // Enable WebSocket by default
    this.wsConnected = false;
  }

  connectedCallback() {
    super.connectedCallback();

    if (this.useWebSocket) {
      this._connectWebSocket();
    } else {
      // Fallback to long polling
      this._startLongPolling();
    }

    // ... rest of existing code ...
  }

  disconnectedCallback() {
    super.disconnectedCallback();

    if (this.wsClient) {
      this.wsClient.disconnect();
      this.wsClient.stopPing();
    }

    this._stopLongPolling();
  }

  _connectWebSocket() {
    this.wsClient = new WebSocketClient(
      '/ws/webchat/',
      (data) => this._handleWebSocketMessage(data),
      (error) => this._handleWebSocketError(error)
    );

    this.wsClient.connect();
    this.wsClient.startPing();
  }

  _handleWebSocketMessage(data) {
    switch (data.type) {
      case 'connection':
        this.wsConnected = true;
        console.log('WebSocket connected:', data);
        break;

      case 'new_message':
        this._handleIncomingMessage(data.message, data.chat_id);
        break;

      case 'typing':
        this._handleTypingIndicator(data);
        break;

      case 'pong':
        // Keepalive response
        break;

      default:
        console.warn('Unknown WebSocket message type:', data.type);
    }
  }

  _handleWebSocketError(error) {
    this.wsConnected = false;
    console.error('WebSocket error, falling back to polling:', error);

    // Fallback to long polling
    this.useWebSocket = false;
    this._startLongPolling();
  }

  _handleIncomingMessage(message, chatId) {
    // Only add if message is for current chat
    if (chatId === this.activeChatId) {
      // Check if message already exists (avoid duplicates)
      if (!this.messages.find(m => m.id === message.id)) {
        this.messages = [...this.messages, message];
        this._scrollToBottom();

        // Show notification if page is not focused
        if (document.hidden) {
          this._showNotification(message);
        }
      }
    }

    // Update chat list last message
    this._updateChatInList(chatId, message);
  }

  _updateChatInList(chatId, message) {
    this.chats = this.chats.map(chat => {
      if (chat.id === chatId) {
        return {
          ...chat,
          last_message: {
            text: message.text,
            timestamp: message.timestamp
          },
          updated_at: message.timestamp
        };
      }
      return chat;
    });

    // Re-sort chats by updated_at
    this.chats.sort((a, b) =>
      new Date(b.updated_at) - new Date(a.updated_at)
    );
  }

  // Fallback: Long polling
  _startLongPolling() {
    if (this._pollingInterval) return;

    this._pollingInterval = setInterval(async () => {
      if (!document.hidden && this.activeChatId) {
        await this._pollMessages();
      }
    }, 3000); // Poll every 3 seconds
  }

  _stopLongPolling() {
    if (this._pollingInterval) {
      clearInterval(this._pollingInterval);
      this._pollingInterval = null;
    }
  }

  async _pollMessages() {
    try {
      const lastMessageId = this.messages[this.messages.length - 1]?.id;
      const response = await fetch(
        `${this.apiBase}/poll/?chat_id=${this.activeChatId}&last_message_id=${lastMessageId || ''}`,
        { credentials: 'same-origin' }
      );

      if (!response.ok) return;

      const data = await response.json();

      if (data.messages.length > 0) {
        this.messages = [...this.messages, ...data.messages];
        this._scrollToBottom();
      }
    } catch (error) {
      console.error('Polling error:', error);
    }
  }
}
```

---

## 5. Typing Indicators

### 5.1 Backend Broadcast
**File**: `unicom/views/webchat_views.py`

```python
@require_http_methods(["POST"])
def typing_indicator_api(request):
    """
    Broadcast typing indicator to chat participants.
    """
    chat_id = request.POST.get('chat_id')
    is_typing = request.POST.get('is_typing', 'true').lower() == 'true'

    if not chat_id:
        return JsonResponse({'error': 'chat_id required'}, status=400)

    # Get account
    from unicom.services.webchat.get_or_create_account import get_or_create_account
    from unicom.models import Channel

    channel = Channel.objects.filter(platform='WebChat', active=True).first()
    account = get_or_create_account(channel, request)

    # Verify access to chat
    from unicom.models import Chat, AccountChat
    try:
        chat = Chat.objects.get(id=chat_id)
        AccountChat.objects.get(account=account, chat=chat)
    except (Chat.DoesNotExist, AccountChat.DoesNotExist):
        return JsonResponse({'error': 'Chat not found'}, status=404)

    # Broadcast typing indicator
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()

    # Get other participants
    other_accounts = AccountChat.objects.filter(chat=chat).exclude(account=account).values_list('account_id', flat=True)

    for account_id in other_accounts:
        group_name = f"webchat_account_{account_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'typing_indicator',
                'chat_id': chat_id,
                'is_typing': is_typing,
                'user_name': account.name or 'User'
            }
        )

    return JsonResponse({'success': True})
```

### 5.2 Frontend Typing Detection
**File**: `unicom/static/unicom/webchat/components/message-input.js`

```javascript
_handleInput(e) {
  this.inputText = e.target.value;

  // Send typing indicator
  this._sendTypingIndicator(true);

  // Clear previous timeout
  if (this._typingTimeout) {
    clearTimeout(this._typingTimeout);
  }

  // Stop typing after 2 seconds of inactivity
  this._typingTimeout = setTimeout(() => {
    this._sendTypingIndicator(false);
  }, 2000);
}

async _sendTypingIndicator(isTyping) {
  // Only send if WebSocket is connected
  if (this.wsConnected) {
    // Send via HTTP API (WebSocket doesn't handle this directly)
    try {
      await fetch(`${this.apiBase}/typing/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': await this._getCSRFToken(),
        },
        body: new URLSearchParams({
          chat_id: this.chatId,
          is_typing: isTyping
        }),
        credentials: 'same-origin'
      });
    } catch (error) {
      // Ignore errors for typing indicators
    }
  }
}
```

### 5.3 Display Typing Indicator
**File**: `unicom/static/unicom/webchat/components/message-list.js`

```javascript
render() {
  return html`
    <div class="message-list">
      ${this.messages.map(msg => html`
        <message-item .message=${msg}></message-item>
      `)}

      ${this.typingUsers.length > 0 ? html`
        <div class="typing-indicator">
          ${this.typingUsers.join(', ')} ${this.typingUsers.length === 1 ? 'is' : 'are'} typing...
        </div>
      ` : ''}
    </div>
  `;
}
```

---

## 6. Browser Notifications

### 6.1 Request Permission
```javascript
async requestNotificationPermission() {
  if ('Notification' in window && Notification.permission === 'default') {
    await Notification.requestPermission();
  }
}

_showNotification(message) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('New message', {
      body: message.text,
      icon: '/static/unicom/icon.png',
      tag: message.chat_id // Prevent duplicate notifications
    });
  }
}
```

---

## Phase 4 Deliverables - What Should Work:

### ✅ WebSocket Implementation
1. **Real-time Messages**: Messages appear instantly without refresh
2. **Connection Management**: Auto-reconnect on disconnect
3. **Fallback Support**: Graceful degradation to long polling
4. **Keepalive**: Ping/pong to maintain connection

### ✅ Long Polling Fallback
1. **Automatic Fallback**: Switch to polling if WebSocket fails
2. **Efficient Polling**: Only poll when page is visible
3. **Incremental Updates**: Fetch only new messages

### ✅ Typing Indicators
1. **Send Indicator**: Broadcast when user is typing
2. **Receive Indicator**: Show when others are typing
3. **Auto-clear**: Stop indicator after inactivity

### ✅ Notifications
1. **Browser Notifications**: Alert user when page is in background
2. **Permission Handling**: Request notification permission
3. **Smart Notifications**: Only notify for unfocused chats

### ✅ User Experience
1. **Instant Delivery**: Messages appear in real-time
2. **Multi-tab Support**: Updates across multiple tabs
3. **Offline Detection**: Show connection status
4. **Smooth Transitions**: No jarring updates

### ⚠️ Known Limitations (to be addressed in Phase 5)
- No read receipts
- No message editing/deletion
- No voice recording (still file upload only)
- No emoji picker
- No message reactions

---

## Success Criteria

Phase 4 is complete when:

1. ✅ Messages appear instantly via WebSocket
2. ✅ Connection auto-reconnects on failure
3. ✅ Long polling works when WebSocket unavailable
4. ✅ Typing indicators show in real-time
5. ✅ Browser notifications work when page unfocused
6. ✅ Multi-tab synchronization works
7. ✅ No duplicate messages appear
8. ✅ Connection status displayed to user
9. ✅ Performance remains smooth with real-time updates
10. ✅ Works reliably across browsers (Chrome, Firefox, Safari, Edge)
