# WebChat Implementation - Phase 3: Multi-Chat Support & ChatGPT-like UX

**Goal**: Enable multiple chat threads per user with a ChatGPT/Claude-style sidebar interface for managing conversations.

**Prerequisites**: Phases 1 & 2 must be complete (backend APIs + basic UI component functional)

---

## 1. Backend Multi-Chat Support

### 1.1 Update Chat ID Strategy

**Current (Phase 1-2)**:
- One chat per account: `Chat.id = Account.id`
- Simple but limits user to single conversation

**New (Phase 3)**:
- Multiple chats per account: `Chat.id = f"webchat_{account.id}_{uuid4()}"`
- OR use database auto-increment and don't rely on predictable IDs
- Maintain Account-Chat relationship via AccountChat model

### 1.2 Chat Metadata
**Update Chat model fields** (optional, may already exist):
- `title`: User-editable chat title (auto-generated from first message if not set)
- `created_at`: When chat was created
- `updated_at`: Last activity timestamp
- `is_archived`: Whether chat is archived

### 1.3 New API Endpoints

#### 1.3.1 Create New Chat
**Endpoint**: `POST /unicom/webchat/chat/create/`

**Request body**:
```json
{
  "title": "Optional initial title",
  "channel_id": 1  // optional
}
```

**Functionality**:
- Create new Chat for current user's Account
- Generate unique chat ID
- Link Account to Chat via AccountChat
- Return chat details

**Response**:
```json
{
  "success": true,
  "chat": {
    "id": "webchat_user123_abc-def-ghi",
    "title": "New Chat",
    "created_at": "2025-10-23T12:00:00Z",
    "message_count": 0
  }
}
```

#### 1.3.2 Update Chat
**Endpoint**: `PATCH /unicom/webchat/chat/<chat_id>/`

**Request body**:
```json
{
  "title": "My Important Conversation",
  "is_archived": false
}
```

**Functionality**:
- Update chat title or archive status
- **Security**: Only allow updates if user is participant in chat

**Response**:
```json
{
  "success": true,
  "chat": {
    "id": "webchat_user123_abc-def-ghi",
    "title": "My Important Conversation",
    "is_archived": false
  }
}
```

#### 1.3.3 Delete/Archive Chat
**Endpoint**: `DELETE /unicom/webchat/chat/<chat_id>/`

**Functionality**:
- Soft delete: Set `is_archived = True`
- OR hard delete: Remove chat and messages (optional)
- **Security**: Only allow deletion if user is participant

**Response**:
```json
{
  "success": true,
  "message": "Chat archived"
}
```

#### 1.3.4 Enhanced List Chats
**Endpoint**: `GET /unicom/webchat/chats/` (update existing)

**New features**:
- Sort by `updated_at` DESC (most recent first)
- Include message count
- Include last message preview
- Filter by `is_archived`
- Support search by title

**Query parameters**:
- `archived`: true/false (default: false)
- `search`: Search in chat title
- `limit`: Pagination limit (default: 20)
- `offset`: Pagination offset

**Response**:
```json
{
  "success": true,
  "chats": [
    {
      "id": "webchat_user123_abc",
      "title": "Technical Support",
      "created_at": "2025-10-23T10:00:00Z",
      "updated_at": "2025-10-23T12:30:00Z",
      "message_count": 15,
      "last_message": {
        "text": "Thanks for your help!",
        "timestamp": "2025-10-23T12:30:00Z",
        "is_outgoing": false
      },
      "is_archived": false
    }
  ],
  "total": 5,
  "has_more": false
}
```

### 1.4 Auto-Generate Chat Titles

**File**: `unicom/services/webchat/generate_chat_title.py`

**Functionality**:
- When first message is sent to a new chat
- If chat has no title, auto-generate from first user message
- Options:
  - **Simple**: Use first 50 chars of first message
  - **Smart** (optional): Use LLM to generate descriptive title

```python
def generate_chat_title(chat: Chat) -> str:
    """
    Auto-generate chat title from first user message.
    """
    first_message = chat.messages.filter(
        is_outgoing=False
    ).order_by('timestamp').first()

    if not first_message:
        return "New Chat"

    # Simple approach: truncate first message
    text = first_message.text or "New Chat"
    title = text[:50] + "..." if len(text) > 50 else text

    # Optional: LLM-based title generation
    # title = generate_title_with_llm(text)

    chat.name = title
    chat.save(update_fields=['name'])
    return title
```

**Integration**:
- Call after saving first message in chat
- Or trigger via signal when message count reaches 1

---

## 2. UI Component Updates

### 2.1 New Component: Chat Sidebar
**File**: `unicom/static/unicom/webchat/components/chat-sidebar.js`

**Features**:
- List of user's chats
- "New Chat" button at top
- Click chat to switch/load messages
- Highlight active chat
- Search/filter chats
- Archive/delete actions (via context menu or swipe)

**Layout**:
```javascript
import { LitElement, html, css } from 'lit';

export class ChatSidebar extends LitElement {
  static properties = {
    chats: { type: Array },
    activeChat: { type: String },
    loading: { type: Boolean, state: true },
    searchQuery: { type: String, state: true },
  };

  render() {
    const filteredChats = this.chats.filter(chat =>
      chat.title.toLowerCase().includes(this.searchQuery.toLowerCase())
    );

    return html`
      <div class="sidebar">
        <div class="sidebar-header">
          <button class="new-chat-btn" @click=${this._handleNewChat}>
            ➕ New Chat
          </button>
          <input
            type="text"
            class="search-input"
            placeholder="Search chats..."
            .value=${this.searchQuery}
            @input=${this._handleSearch}>
        </div>

        <div class="chat-list">
          ${this.loading ? html`<div class="loading">Loading...</div>` : ''}

          ${filteredChats.map(chat => html`
            <div
              class="chat-item ${chat.id === this.activeChat ? 'active' : ''}"
              @click=${() => this._handleChatClick(chat.id)}>

              <div class="chat-title">${chat.title}</div>
              <div class="chat-preview">${chat.last_message?.text || 'No messages'}</div>
              <div class="chat-time">${this._formatTime(chat.updated_at)}</div>

              <button
                class="chat-menu"
                @click=${(e) => this._handleMenuClick(e, chat)}>
                ⋮
              </button>
            </div>
          `)}
        </div>
      </div>
    `;
  }

  _handleNewChat() {
    this.dispatchEvent(new CustomEvent('new-chat'));
  }

  _handleChatClick(chatId) {
    this.dispatchEvent(new CustomEvent('select-chat', {
      detail: { chatId }
    }));
  }

  _handleMenuClick(e, chat) {
    e.stopPropagation();
    this.dispatchEvent(new CustomEvent('chat-menu', {
      detail: { chat, x: e.clientX, y: e.clientY }
    }));
  }
}

customElements.define('chat-sidebar', ChatSidebar);
```

### 2.2 Update Main Component
**File**: `unicom/static/unicom/webchat/webchat-component.js`

**Add sidebar integration**:
```javascript
export class UnicomChat extends LitElement {
  static properties = {
    // ... existing properties ...
    showSidebar: { type: Boolean, attribute: 'show-sidebar' },
    chats: { type: Array, state: true },
    activeChatId: { type: String, state: true },
  };

  constructor() {
    super();
    // ... existing code ...
    this.showSidebar = true; // Enable by default in Phase 3
    this.chats = [];
  }

  async connectedCallback() {
    super.connectedCallback();
    if (this.showSidebar) {
      await this.loadChats();
    }
    // Load messages for active chat
    await this.loadMessages();
  }

  render() {
    return html`
      <div class="unicom-chat-container ${this.theme} ${this.showSidebar ? 'with-sidebar' : ''}">
        ${this.showSidebar ? html`
          <chat-sidebar
            .chats=${this.chats}
            .activeChat=${this.activeChatId}
            @new-chat=${this._handleNewChat}
            @select-chat=${this._handleSelectChat}
            @chat-menu=${this._handleChatMenu}>
          </chat-sidebar>
        ` : ''}

        <div class="chat-main">
          ${this.error ? html`<div class="error">${this.error}</div>` : ''}

          <div class="chat-header">
            ${this.showSidebar && this.activeChat ? html`
              <div class="chat-header-title" @click=${this._handleEditTitle}>
                ${this.activeChat.title}
              </div>
            ` : ''}
          </div>

          <message-list
            .messages=${this.messages}
            .loading=${this.loading}
            @load-more=${this._handleLoadMore}>
          </message-list>

          <message-input
            .disabled=${this.sending}
            @send-message=${this._handleSendMessage}
            @send-media=${this._handleSendMedia}>
          </message-input>
        </div>
      </div>
    `;
  }

  async loadChats() {
    try {
      this.loading = true;
      const data = await this.api.getChats({ archived: false });
      this.chats = data.chats;

      // Set active chat to most recent if not set
      if (!this.activeChatId && this.chats.length > 0) {
        this.activeChatId = this.chats[0].id;
      }
    } catch (error) {
      this.error = 'Failed to load chats';
    } finally {
      this.loading = false;
    }
  }

  async _handleNewChat() {
    try {
      const data = await this.api.createChat();
      this.chats = [data.chat, ...this.chats];
      this.activeChatId = data.chat.id;
      this.messages = []; // Clear messages for new chat
    } catch (error) {
      this.error = 'Failed to create chat';
    }
  }

  async _handleSelectChat(e) {
    const { chatId } = e.detail;
    this.activeChatId = chatId;
    await this.loadMessages();
  }

  async _handleChatMenu(e) {
    const { chat, x, y } = e.detail;
    // Show context menu with Archive/Delete options
    this._showContextMenu(chat, x, y);
  }
}
```

### 2.3 Context Menu Component
**File**: `unicom/static/unicom/webchat/components/context-menu.js`

**Features**:
- Rename chat
- Archive chat
- Delete chat (with confirmation)
- Position near click location

```javascript
export class ContextMenu extends LitElement {
  render() {
    return html`
      <div class="context-menu" style="left: ${this.x}px; top: ${this.y}px">
        <button @click=${() => this._emit('rename')}>Rename</button>
        <button @click=${() => this._emit('archive')}>Archive</button>
        <button @click=${() => this._emit('delete')} class="danger">Delete</button>
      </div>
    `;
  }

  _emit(action) {
    this.dispatchEvent(new CustomEvent('action', {
      detail: { action, chat: this.chat }
    }));
  }
}
```

### 2.4 Responsive Sidebar
**CSS for mobile**:
```css
@media (max-width: 768px) {
  .unicom-chat-container.with-sidebar {
    display: flex;
  }

  chat-sidebar {
    position: absolute;
    left: -100%;
    transition: left 0.3s;
    z-index: 100;
  }

  .unicom-chat-container.sidebar-open chat-sidebar {
    left: 0;
  }

  /* Hamburger menu to toggle sidebar on mobile */
  .chat-header .menu-btn {
    display: block;
  }
}
```

---

## 3. Enhanced Message Handling

### 3.1 Update Send Message Logic
When sending message:
- If `activeChatId` exists, send to that chat
- If no active chat, create new chat first, then send message
- After sending, update chat's `updated_at` and last message

### 3.2 Update Auto-Refresh
- When polling for new messages, also refresh chat list (less frequently)
- Update chat last message preview when new messages arrive
- Show notification badge on sidebar for chats with new messages (optional)

---

## 4. Data Management

### 4.1 Chat Persistence
- Store `activeChatId` in localStorage
- On component load, restore last active chat
- Preserve state across page refreshes

```javascript
connectedCallback() {
  super.connectedCallback();

  // Restore active chat from localStorage
  const savedChatId = localStorage.getItem('unicom-active-chat');
  if (savedChatId) {
    this.activeChatId = savedChatId;
  }

  this.loadChats();
}

async _handleSelectChat(e) {
  const { chatId } = e.detail;
  this.activeChatId = chatId;

  // Save to localStorage
  localStorage.setItem('unicom-active-chat', chatId);

  await this.loadMessages();
}
```

### 4.2 Optimistic Updates
When user sends message:
1. Immediately add message to UI (optimistic)
2. Send API request
3. If success, update message ID
4. If fail, show error and remove optimistic message

```javascript
async _handleSendMessage(e) {
  const { text } = e.detail;

  // Optimistic update
  const tempMessage = {
    id: `temp-${Date.now()}`,
    text,
    is_outgoing: true,
    timestamp: new Date().toISOString(),
    sender_name: 'You',
    media_type: 'text',
    _pending: true,
  };

  this.messages = [...this.messages, tempMessage];
  this._scrollToBottom();

  try {
    this.sending = true;
    const data = await this.api.sendMessage(text, this.activeChatId);

    // Replace temp message with real one
    this.messages = this.messages.map(msg =>
      msg.id === tempMessage.id ? data.message : msg
    );

  } catch (error) {
    // Remove temp message on error
    this.messages = this.messages.filter(msg => msg.id !== tempMessage.id);
    this.error = 'Failed to send message';
  } finally {
    this.sending = false;
  }
}
```

---

## 5. Guest User Multi-Chat

### 5.1 Guest Limitations
For Phase 3, guest users:
- **Option A**: Still limited to single chat (simpler)
- **Option B**: Can create multiple chats but they're session-only (lost on logout)

**Recommended**: Option A (keep single chat for guests, multi-chat for authenticated users only)

### 5.2 Migration Update
**File**: `unicom/services/webchat/migrate_guest_to_user.py`

**Update to handle multiple chats** (if Option B chosen):
```python
def migrate_guest_to_user(old_session_key: str, user: User) -> Account:
    """
    Migrate all guest chats to authenticated user.
    """
    guest_account_id = f"webchat_guest_{old_session_key}"
    user_account_id = f"webchat_user_{user.id}"

    # Get or create user account
    user_account, created = Account.objects.get_or_create(
        id=user_account_id,
        defaults={
            'platform': 'WebChat',
            'channel': get_webchat_channel(),
            'name': user.get_full_name() or user.username,
        }
    )

    # Find guest account
    try:
        guest_account = Account.objects.get(id=guest_account_id)
    except Account.DoesNotExist:
        return user_account  # No guest data to migrate

    # Transfer all chats from guest to user
    guest_chats = AccountChat.objects.filter(account=guest_account)

    for account_chat in guest_chats:
        chat = account_chat.chat

        # Update all messages sender
        chat.messages.filter(sender=guest_account).update(sender=user_account)

        # Re-link chat to user account
        AccountChat.objects.create(account=user_account, chat=chat)

    # Delete guest account
    guest_account.delete()

    return user_account
```

---

## 6. Advanced Features

### 6.1 Chat Search
**Add search within chat messages**:
```javascript
_handleSearchMessages(query) {
  // Highlight matching messages
  // Or filter message list to show only matches
}
```

### 6.2 Unread Message Count
**Backend**:
- Track last read message per user per chat
- Return unread count in chat list API

**Frontend**:
- Display badge with unread count on sidebar
- Mark messages as read when chat is opened

---

## Phase 3 Deliverables - What Should Work:

### ✅ Multi-Chat Backend
1. **Multiple Chats**: Users can create unlimited chat threads
2. **Chat CRUD**: Create, read, update, delete (archive) chats
3. **Chat Metadata**: Titles, timestamps, message counts
4. **Auto-Titles**: Chats auto-generate titles from first message

### ✅ Chat Sidebar UI
1. **Chat List**: Scrollable list of user's chats
2. **New Chat Button**: Create new chat with one click
3. **Chat Preview**: Show last message and timestamp
4. **Active Highlight**: Visual indicator for selected chat
5. **Search**: Filter chats by title
6. **Context Menu**: Rename, archive, delete chats

### ✅ Chat Switching
1. **Instant Switch**: Click chat to load its messages
2. **State Persistence**: Remember active chat across page reloads
3. **Optimistic Updates**: Instant UI feedback when sending

### ✅ Enhanced UX
1. **ChatGPT-like Layout**: Sidebar + main chat area
2. **Responsive**: Collapsible sidebar on mobile
3. **Empty States**: Friendly messages for no chats/messages
4. **Loading States**: Smooth transitions between chats

### ✅ Data Management
1. **Local Storage**: Persist active chat preference
2. **Optimistic Rendering**: Messages appear instantly before API confirms
3. **Error Recovery**: Graceful handling of failed sends

### ⚠️ Known Limitations (to be addressed in later phases)
- No real-time notifications for new messages in background chats
- No unread message badges (Phase 4/5)
- No message search within chat (Phase 5)
- Guest users limited to single chat (if Option A chosen)
- No chat folders/categories

---

## Success Criteria

Phase 3 is complete when:

1. ✅ User can create multiple chat threads
2. ✅ Sidebar lists all user's chats
3. ✅ Clicking chat loads its message history
4. ✅ New messages go to active chat
5. ✅ User can rename chat titles
6. ✅ User can archive/delete chats
7. ✅ Search filters chat list
8. ✅ Active chat persists across page refresh
9. ✅ Optimistic UI updates work correctly
10. ✅ Sidebar is responsive on mobile
11. ✅ Auto-generated chat titles are descriptive
12. ✅ Guest-to-user migration preserves all chats (if multi-chat for guests enabled)
