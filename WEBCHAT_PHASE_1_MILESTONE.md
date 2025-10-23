# WebChat Implementation - Phase 1: Backend Foundation

**Goal**: Create a fully functional WebChat backend that integrates seamlessly with unicom's existing architecture.

---

## 1. Platform Registration

### 1.1 Add WebChat to Platform Constants
**Files to modify**:
- `unicom/models/constants.py`

**Changes**:
```python
channels = [
    ('Email', 'Email'),
    ('Telegram', 'Telegram'),
    ('WhatsApp', 'WhatsApp'),
    ('Internal', 'Internal'),
    ('WebChat', 'WebChat'),  # NEW
]
```

---

## 2. WebChat Service Layer

### 2.1 Create WebChat Services Directory
**Directory structure**:
```
unicom/services/webchat/
├── __init__.py
├── save_webchat_message.py
├── send_webchat_message.py
└── get_or_create_account.py
```

### 2.2 Account Management Service
**File**: `unicom/services/webchat/get_or_create_account.py`

**Functionality**:
- Accept `request` object (Django HTTP request)
- Detect if user is authenticated or guest
- For authenticated users:
  - Account ID: `f"webchat_user_{request.user.id}"`
  - Link to Member model automatically if exists
  - Auto-create Member if user has no Member
- For guest users:
  - Account ID: `f"webchat_guest_{request.session.session_key}"`
  - Ensure session is created if doesn't exist
- Create Account if doesn't exist
- Return Account object

**Function signature**:
```python
def get_or_create_account(
    channel: Channel,
    request: HttpRequest
) -> Account:
    """
    Get or create WebChat account based on Django auth state.
    Creates session for guests if needed.
    Links authenticated users to Member model.
    """
```

### 2.3 Save Incoming Message Service
**File**: `unicom/services/webchat/save_webchat_message.py`

**Functionality**:
- Similar pattern to `save_telegram_message`
- Accept: channel, message_data dict, user (optional), request (for account detection)
- Message data structure:
  ```python
  {
      'text': str,  # Required
      'chat_id': str,  # Optional - if not provided, use Account.id as chat_id
      'media_type': str,  # 'text', 'image', 'audio' (default: 'text')
      'file': UploadedFile,  # Optional - for media messages
  }
  ```
- Get or create Account using `get_or_create_account`
- Get or create Chat:
  - If `chat_id` provided, use it
  - Otherwise, create/get chat with ID = Account.id (single chat per account for Phase 1)
- Create Message object
- Handle media uploads (images, audio files)
- **Create Request object** (for incoming messages only)
- Return Message object

**Function signature**:
```python
def save_webchat_message(
    channel: Channel,
    message_data: dict,
    request: HttpRequest,
    user: User = None
) -> Message:
    """
    Save a WebChat message and create Request for processing.
    Auto-creates Account, Chat, and Request as needed.
    """
```

### 2.4 Send Outgoing Message Service
**File**: `unicom/services/webchat/send_webchat_message.py`

**Functionality**:
- Similar pattern to `send_telegram_message`
- Accept: channel, msg dict, user (optional)
- Message dict structure:
  ```python
  {
      'chat_id': str,  # Required
      'text': str,  # Required (or html)
      'html': str,  # Optional - rich HTML content
      'file_path': str,  # Optional - path to media file
      'media_type': str,  # 'text', 'html', 'image', 'audio'
  }
  ```
- Get Chat by ID
- Get Account from Chat (first account associated with chat)
- Create outgoing Message object (is_outgoing=True)
- Handle media files if provided
- Return Message object
- **Note**: WebChat doesn't need external API calls - messages are stored in DB only

**Function signature**:
```python
def send_webchat_message(
    channel: Channel,
    msg: dict,
    user: User = None
) -> Message:
    """
    Send a WebChat message (save to database).
    Used by bots/system to send messages to users.
    """
```

---

## 3. Update Crossplatform Services

### 3.1 Update `send_message.py`
**File**: `unicom/services/crossplatform/send_message.py`

**Add**:
```python
from unicom.services.webchat.send_webchat_message import send_webchat_message

def send_message(channel: Channel, msg:dict, user:User=None) -> Message:
    # ... existing code ...
    elif channel.platform == 'WebChat':
        return send_webchat_message(channel, msg, user)
```

---

## 4. REST API Endpoints

### 4.1 Create WebChat Views
**File**: `unicom/views/webchat_views.py`

#### 4.1.1 Send Message API
**Endpoint**: `POST /unicom/webchat/send/`

**Authentication**:
- Django session authentication (works for both authenticated and guest users)
- CSRF protection required

**Request body**:
```json
{
  "text": "Hello!",
  "chat_id": "optional - if not provided, uses/creates default chat",
  "media": "optional - file upload via multipart/form-data"
}
```

**Functionality**:
- Get or create WebChat Channel (auto-create if doesn't exist, or require channel_id in request)
- Call `save_webchat_message` to save incoming message
- Message automatically creates Request which flows through categorization/bot processing
- Return message details + chat_id

**Response**:
```json
{
  "success": true,
  "message": {
    "id": "message_id",
    "text": "Hello!",
    "timestamp": "2025-10-23T12:00:00Z",
    "chat_id": "webchat_user_123"
  }
}
```

#### 4.1.2 Get Messages API
**Endpoint**: `GET /unicom/webchat/messages/`

**Query parameters**:
- `chat_id` (optional - defaults to user's default chat)
- `limit` (optional - default: 50, max: 100)
- `before` (optional - message ID for pagination, get messages before this ID)
- `after` (optional - message ID for pagination, get messages after this ID)

**Functionality**:
- Get or create Account for current user
- If no `chat_id` provided, use Account.id as chat_id
- Filter messages by chat_id
- **Security**: Only return messages from chats where user's Account is a participant
- Order by timestamp descending
- Support pagination using `before`/`after` cursors

**Response**:
```json
{
  "success": true,
  "chat_id": "webchat_user_123",
  "messages": [
    {
      "id": "msg_1",
      "text": "Hello!",
      "is_outgoing": false,
      "sender_name": "John Doe",
      "timestamp": "2025-10-23T12:00:00Z",
      "media_type": "text",
      "media_url": null
    }
  ],
  "has_more": true,
  "next_cursor": "msg_0"
}
```

#### 4.1.3 List Chats API
**Endpoint**: `GET /unicom/webchat/chats/`

**Query parameters**:
- `channel_id` (optional - filter by channel)
- Custom filter parameters (passed through to queryset filter)
  - Example: `?status=active&archived=false`
  - Any valid Chat model field can be used as filter

**Functionality**:
- Get Account for current user
- Find all chats where user's Account is a participant (via AccountChat)
- **Security**: Only return chats where user is a participant
- Apply additional filters from query parameters
- Return chat list with metadata (last message, unread count, etc.)

**Response**:
```json
{
  "success": true,
  "chats": [
    {
      "id": "webchat_user_123",
      "name": "My Chat",
      "platform": "WebChat",
      "channel_id": 1,
      "last_message": {
        "text": "Latest message",
        "timestamp": "2025-10-23T12:00:00Z"
      },
      "is_archived": false
    }
  ]
}
```

### 4.2 Update URL Configuration
**File**: `unicom/urls.py`

**Add**:
```python
from unicom.views.webchat_views import (
    send_webchat_message_api,
    get_webchat_messages_api,
    list_webchat_chats_api,
)

urlpatterns = [
    # ... existing patterns ...
    path('webchat/send/', send_webchat_message_api, name='webchat_send'),
    path('webchat/messages/', get_webchat_messages_api, name='webchat_messages'),
    path('webchat/chats/', list_webchat_chats_api, name='webchat_chats'),
]
```

---

## 5. Channel Management

### 5.1 WebChat Channel Creation
**Options**:

**Option A: Auto-create WebChat channel**
- On first WebChat API call, check if WebChat channel exists
- If not, auto-create with default config
- Store in settings: `WEBCHAT_CHANNEL_ID` or dynamically find by platform='WebChat'

**Option B: Manual creation** (RECOMMENDED)
- Admin creates WebChat channel via Django admin
- Pass `channel_id` in API requests OR
- Use first active WebChat channel if exists

**Recommended**: Option B with fallback to first active WebChat channel

### 5.2 Channel Validation
**File**: `unicom/models/channel.py` (update `validate()` method)

**Add**:
```python
elif self.platform == 'WebChat':
    # WebChat doesn't need external validation
    # Just mark as active
    self.active = True
    self.error = None
```

---

## 6. Guest to Authenticated User Migration

### 6.1 Migration Utility
**File**: `unicom/services/webchat/migrate_guest_to_user.py`

**Functionality**:
- Detect when guest user logs in/registers
- Find guest Account: `webchat_guest_{old_session_key}`
- Create new Account: `webchat_user_{user.id}`
- Transfer all messages, chats from guest account to user account
- Link to Member model
- Delete guest account

**Function signature**:
```python
def migrate_guest_to_user(
    old_session_key: str,
    user: User
) -> Account:
    """
    Migrate guest webchat data to authenticated user.
    Called after user login/registration.
    """
```

### 6.2 Signal Handler
**File**: `unicom/signals.py` (create if doesn't exist)

**Add**:
```python
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

@receiver(user_logged_in)
def migrate_webchat_guest_data(sender, request, user, **kwargs):
    """Auto-migrate guest webchat data on login"""
    if hasattr(request, 'session') and request.session.session_key:
        from unicom.services.webchat.migrate_guest_to_user import migrate_guest_to_user
        try:
            migrate_guest_to_user(request.session.session_key, user)
        except Exception as e:
            # Log error but don't block login
            print(f"WebChat migration error: {e}")
```

---

## 7. Testing & Validation

### 7.1 Manual API Testing
Create test scripts to validate:
- Guest user sends message → creates Account, Chat, Message, Request
- Authenticated user sends message → uses correct Account ID
- Get messages API returns only user's messages
- List chats API returns only user's chats
- Guest login migration works correctly

### 7.2 Integration with Request Flow
Test that:
- WebChat messages create Request objects
- Requests go through identify_member → categorize → process flow
- Bot can reply via `message.reply_with()`
- Bot replies appear in get messages API

---

## Phase 1 Deliverables - What Should Work:

### ✅ Backend Functionality
1. **Platform Support**: WebChat platform registered and recognized throughout unicom
2. **Account Management**: Automatic account creation for both authenticated and guest users
3. **Message Storage**: Incoming and outgoing messages saved to database
4. **Request Creation**: Incoming messages automatically create Request objects
5. **Integration**: WebChat works with existing Request categorization and Bot processing
6. **API Endpoints**:
   - Send message (creates Message + Request)
   - Get messages (paginated, filtered by chat)
   - List chats (filtered by user, supports custom filters)

### ✅ Security
1. Users can only access their own chats and messages
2. CSRF protection on all POST endpoints
3. Django session authentication

### ✅ Data Flow
```
User sends message via API
  → save_webchat_message creates Message + Request
  → Request flows through: identify_member → categorize → process (Bot)
  → Bot replies via message.reply_with()
  → Reply saved as outgoing Message
  → User fetches messages via GET API
  → User sees bot reply
```

### ✅ Guest Support
1. Guest users get session-based accounts
2. Guest accounts automatically migrate to user accounts on login
3. Chat history preserved during migration

### ⚠️ Known Limitations (to be addressed in later phases)
- No WebSocket/real-time updates (requires page refresh/polling)
- No UI component (Phase 2)
- Single chat per account (multi-chat support in Phase 3)
- Basic text messages only (rich media in Phase 2)
- No typing indicators
- No read receipts

---

## Success Criteria

Phase 1 is complete when:

1. ✅ You can send a message via `POST /unicom/webchat/send/` as a guest
2. ✅ Message appears in `GET /unicom/webchat/messages/`
3. ✅ Message creates a Request that a Bot can process
4. ✅ Bot reply appears in messages API
5. ✅ Guest user can log in and their chat history is preserved
6. ✅ Authenticated users have persistent chat history across sessions
7. ✅ All APIs respect user access controls (users can't see others' chats)
