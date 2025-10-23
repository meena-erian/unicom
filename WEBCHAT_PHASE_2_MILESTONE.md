# WebChat Implementation - Phase 2: LitElement UI Component

**Goal**: Create a modular, customizable LitElement web component for chat interface with support for rich media messages.

**Prerequisites**: Phase 1 must be complete (all backend APIs functional)

---

## 1. LitElement Component Structure

### 1.1 Create Static Assets Directory
**Directory structure**:
```
unicom/static/unicom/webchat/
├── webchat-component.js       # Main LitElement component
├── webchat-styles.js          # Shared styles and CSS
├── components/
│   ├── message-list.js        # Message list sub-component
│   ├── message-item.js        # Individual message rendering
│   ├── message-input.js       # Input field + send button
│   └── media-preview.js       # Image/audio preview component
└── utils/
    ├── api-client.js          # Wrapper for fetch API calls
    └── datetime-formatter.js  # Format timestamps
```

### 1.2 Install LitElement
**Options**:
- **Option A**: Bundle with build tool (Rollup/Webpack)
- **Option B**: Load from CDN (simpler, recommended for Phase 2)

**File**: `unicom/templates/unicom/webchat_component.html`
```html
<!-- Load Lit from CDN -->
<script type="module" src="https://cdn.jsdelivr.net/npm/lit@3/+esm"></script>
<script type="module" src="{% static 'unicom/webchat/webchat-component.js' %}"></script>
```

---

## 2. Main Component: `<unicom-chat>`

### 2.1 Component Definition
**File**: `unicom/static/unicom/webchat/webchat-component.js`

**Features**:
- Custom element: `<unicom-chat>`
- Properties (attributes):
  - `api-base`: API endpoint base URL (default: '/unicom/webchat')
  - `chat-id`: Optional chat ID (defaults to user's primary chat)
  - `channel-id`: Optional channel ID
  - `max-messages`: Max messages to display (default: 50)
  - `theme`: 'light' or 'dark' (default: 'light')
  - `auto-refresh`: Seconds between refreshes (default: 5, 0 to disable)

**CSS Custom Properties** (for theming):
```css
--unicom-primary-color: #007bff;
--unicom-secondary-color: #6c757d;
--unicom-background-color: #ffffff;
--unicom-message-bg-incoming: #f1f3f4;
--unicom-message-bg-outgoing: #007bff;
--unicom-message-text-outgoing: #ffffff;
--unicom-text-color: #212529;
--unicom-border-color: #dee2e6;
--unicom-border-radius: 8px;
--unicom-font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
--unicom-input-height: 48px;
--unicom-max-width: 800px;
```

**Component Structure**:
```javascript
import { LitElement, html, css } from 'lit';

export class UnicomChat extends LitElement {
  static properties = {
    apiBase: { type: String, attribute: 'api-base' },
    chatId: { type: String, attribute: 'chat-id' },
    channelId: { type: Number, attribute: 'channel-id' },
    maxMessages: { type: Number, attribute: 'max-messages' },
    theme: { type: String },
    autoRefresh: { type: Number, attribute: 'auto-refresh' },

    // Internal state
    messages: { type: Array, state: true },
    loading: { type: Boolean, state: true },
    sending: { type: Boolean, state: true },
    error: { type: String, state: true },
  };

  constructor() {
    super();
    this.apiBase = '/unicom/webchat';
    this.maxMessages = 50;
    this.theme = 'light';
    this.autoRefresh = 5;
    this.messages = [];
    this.loading = false;
    this.sending = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this.loadMessages();
    if (this.autoRefresh > 0) {
      this._startAutoRefresh();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._stopAutoRefresh();
  }

  render() {
    return html`
      <div class="unicom-chat-container ${this.theme}">
        ${this.error ? html`<div class="error">${this.error}</div>` : ''}
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
    `;
  }

  // Methods for API calls, event handlers, etc.
}

customElements.define('unicom-chat', UnicomChat);
```

### 2.2 API Client Utility
**File**: `unicom/static/unicom/webchat/utils/api-client.js`

**Functions**:
```javascript
export class WebChatAPI {
  constructor(baseURL) {
    this.baseURL = baseURL;
  }

  async getCSRFToken() {
    // Extract CSRF token from cookies
    const name = 'csrftoken';
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [key, value] = cookie.trim().split('=');
      if (key === name) return value;
    }
    return null;
  }

  async sendMessage(text, chatId = null, mediaFile = null) {
    const formData = new FormData();
    formData.append('text', text);
    if (chatId) formData.append('chat_id', chatId);
    if (mediaFile) formData.append('media', mediaFile);

    const response = await fetch(`${this.baseURL}/send/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': await this.getCSRFToken(),
      },
      body: formData,
      credentials: 'same-origin',
    });

    if (!response.ok) throw new Error('Failed to send message');
    return await response.json();
  }

  async getMessages(chatId = null, limit = 50, before = null) {
    const params = new URLSearchParams();
    if (chatId) params.append('chat_id', chatId);
    params.append('limit', limit);
    if (before) params.append('before', before);

    const response = await fetch(`${this.baseURL}/messages/?${params}`, {
      credentials: 'same-origin',
    });

    if (!response.ok) throw new Error('Failed to fetch messages');
    return await response.json();
  }

  async getChats(filters = {}) {
    const params = new URLSearchParams(filters);
    const response = await fetch(`${this.baseURL}/chats/?${params}`, {
      credentials: 'same-origin',
    });

    if (!response.ok) throw new Error('Failed to fetch chats');
    return await response.json();
  }
}
```

---

## 3. Sub-Components

### 3.1 Message List Component
**File**: `unicom/static/unicom/webchat/components/message-list.js`

**Features**:
- Scrollable container for messages
- Auto-scroll to bottom on new messages
- "Load More" button at top for pagination
- Loading spinner
- Inspired by `chat_history_view.py` template

**Rendering**:
```javascript
render() {
  return html`
    <div class="message-list" @scroll=${this._handleScroll}>
      ${this.loading ? html`<div class="loading">Loading...</div>` : ''}

      ${this.hasMore ? html`
        <button @click=${this._loadMore} class="load-more">
          Load earlier messages
        </button>
      ` : ''}

      ${this.messages.map(msg => html`
        <message-item .message=${msg}></message-item>
      `)}
    </div>
  `;
}
```

### 3.2 Message Item Component
**File**: `unicom/static/unicom/webchat/components/message-item.js`

**Features**:
- Render individual message
- Support multiple media types: text, html, image, audio
- Different styles for incoming vs outgoing
- Timestamp formatting
- Inspired by chat_history.html template message rendering

**Media Type Handling** (following chat_history_view pattern):
```javascript
_renderMessageContent(message) {
  switch (message.media_type) {
    case 'text':
      return html`<div class="message-text">${message.text}</div>`;

    case 'html':
      // Sanitize HTML before rendering
      return html`<div class="message-html" .innerHTML=${this._sanitizeHTML(message.html || message.text)}></div>`;

    case 'image':
      return html`
        <div class="message-media">
          ${message.text && message.text !== '**Image**' ?
            html`<div class="message-caption">${message.text}</div>` : ''}
          <img src="${message.media_url}" alt="Image" @click=${() => this._openImageModal(message.media_url)}>
        </div>
      `;

    case 'audio':
      return html`
        <div class="message-media">
          ${message.text && message.text !== '**Voice Message**' ?
            html`<div class="message-caption">${message.text}</div>` : ''}
          <audio controls src="${message.media_url}"></audio>
        </div>
      `;

    case 'tool_call':
    case 'tool_response':
      // Display as system message with special styling
      return html`<div class="message-system">${message.text}</div>`;

    default:
      return html`<div class="message-text">${message.text}</div>`;
  }
}

render() {
  const message = this.message;
  const isOutgoing = message.is_outgoing;
  const alignment = isOutgoing ? 'outgoing' : 'incoming';

  return html`
    <div class="message-item ${alignment}">
      ${!isOutgoing ? html`<div class="sender-name">${message.sender_name}</div>` : ''}
      <div class="message-bubble">
        ${this._renderMessageContent(message)}
        <div class="message-timestamp">${this._formatTimestamp(message.timestamp)}</div>
      </div>
    </div>
  `;
}
```

### 3.3 Message Input Component
**File**: `unicom/static/unicom/webchat/components/message-input.js`

**Features**:
- Text input field (textarea that expands)
- Send button
- Media upload button (image/audio)
- File preview before sending
- Keyboard shortcuts (Enter to send, Shift+Enter for new line)

**Layout**:
```javascript
render() {
  return html`
    <div class="message-input-container">
      ${this.previewFile ? html`
        <media-preview
          .file=${this.previewFile}
          @remove=${this._handleRemoveFile}>
        </media-preview>
      ` : ''}

      <div class="input-row">
        <input
          type="file"
          id="media-upload"
          accept="image/*,audio/*"
          @change=${this._handleFileSelect}
          style="display: none;">

        <button
          class="attach-btn"
          @click=${() => this.shadowRoot.getElementById('media-upload').click()}
          ?disabled=${this.disabled}>
          📎
        </button>

        <textarea
          .value=${this.inputText}
          @input=${this._handleInput}
          @keydown=${this._handleKeyDown}
          placeholder="Type a message..."
          ?disabled=${this.disabled}
          rows="1">
        </textarea>

        <button
          class="send-btn"
          @click=${this._handleSend}
          ?disabled=${this.disabled || (!this.inputText.trim() && !this.previewFile)}>
          Send
        </button>
      </div>
    </div>
  `;
}

_handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    this._handleSend();
  }
}
```

### 3.4 Media Preview Component
**File**: `unicom/static/unicom/webchat/components/media-preview.js`

**Features**:
- Preview selected image/audio before sending
- Remove button
- Display file name and size

---

## 4. Styling System

### 4.1 Shared Styles
**File**: `unicom/static/unicom/webchat/webchat-styles.js`

**Export common styles**:
```javascript
import { css } from 'lit';

export const baseStyles = css`
  :host {
    /* CSS custom properties */
    --primary-color: var(--unicom-primary-color, #007bff);
    --background: var(--unicom-background-color, #ffffff);
    --text-color: var(--unicom-text-color, #212529);
    --border-radius: var(--unicom-border-radius, 8px);
    /* ... all custom properties ... */

    display: block;
    font-family: var(--unicom-font-family, sans-serif);
    max-width: var(--unicom-max-width, 800px);
    margin: 0 auto;
  }

  .unicom-chat-container {
    display: flex;
    flex-direction: column;
    height: 600px;
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    background: var(--background);
    overflow: hidden;
  }

  .unicom-chat-container.dark {
    --background: #1e1e1e;
    --text-color: #ffffff;
    --border-color: #444;
    --message-bg-incoming: #2d2d2d;
  }
`;

export const messageStyles = css`
  .message-item {
    padding: 8px 16px;
    display: flex;
    flex-direction: column;
  }

  .message-item.outgoing {
    align-items: flex-end;
  }

  .message-item.incoming {
    align-items: flex-start;
  }

  .message-bubble {
    max-width: 70%;
    padding: 12px 16px;
    border-radius: var(--border-radius);
    word-wrap: break-word;
  }

  .outgoing .message-bubble {
    background: var(--unicom-message-bg-outgoing);
    color: var(--unicom-message-text-outgoing);
  }

  .incoming .message-bubble {
    background: var(--unicom-message-bg-incoming);
    color: var(--text-color);
  }

  .message-timestamp {
    font-size: 0.75rem;
    opacity: 0.7;
    margin-top: 4px;
  }

  .message-media img {
    max-width: 100%;
    border-radius: 4px;
    cursor: pointer;
  }

  .message-media audio {
    width: 100%;
  }
`;
```

### 4.2 Theme Presets
Create pre-defined themes users can choose:

```javascript
export const themes = {
  light: {
    '--unicom-background-color': '#ffffff',
    '--unicom-text-color': '#212529',
    '--unicom-message-bg-incoming': '#f1f3f4',
    '--unicom-message-bg-outgoing': '#007bff',
  },
  dark: {
    '--unicom-background-color': '#1e1e1e',
    '--unicom-text-color': '#ffffff',
    '--unicom-message-bg-incoming': '#2d2d2d',
    '--unicom-message-bg-outgoing': '#0056b3',
  },
  // Add more themes...
};
```

---

## 5. Django Integration

### 5.1 Template Tag
**File**: `unicom/templatetags/unicom_tags.py`

```python
from django import template
from django.utils.safestring import mark_safe
from django.templatetags.static import static

register = template.Library()

@register.simple_tag
def webchat_component(
    api_base='/unicom/webchat',
    chat_id=None,
    channel_id=None,
    theme='light',
    max_messages=50,
    auto_refresh=5,
    **custom_styles
):
    """
    Render the WebChat LitElement component.

    Usage:
        {% load unicom_tags %}
        {% webchat_component theme="dark" primary_color="#ff5722" %}
    """
    attrs = [
        f'api-base="{api_base}"',
        f'theme="{theme}"',
        f'max-messages="{max_messages}"',
        f'auto-refresh="{auto_refresh}"',
    ]

    if chat_id:
        attrs.append(f'chat-id="{chat_id}"')
    if channel_id:
        attrs.append(f'channel-id="{channel_id}"')

    # Build inline style for custom CSS properties
    styles = []
    css_var_mapping = {
        'primary_color': '--unicom-primary-color',
        'background_color': '--unicom-background-color',
        'text_color': '--unicom-text-color',
        'border_radius': '--unicom-border-radius',
        # ... add all supported custom properties
    }

    for key, css_var in css_var_mapping.items():
        if key in custom_styles:
            styles.append(f'{css_var}: {custom_styles[key]}')

    style_attr = f'style="{"; ".join(styles)}"' if styles else ''

    html = f'''
    <link rel="stylesheet" href="{static("unicom/webchat/webchat.css")}">
    <script type="module" src="https://cdn.jsdelivr.net/npm/lit@3/+esm"></script>
    <script type="module" src="{static("unicom/webchat/webchat-component.js")}"></script>
    <unicom-chat {" ".join(attrs)} {style_attr}></unicom-chat>
    '''

    return mark_safe(html)
```

### 5.2 Example Usage in Django Template
```django
{% load unicom_tags %}

<!DOCTYPE html>
<html>
<head>
    <title>WebChat Demo</title>
</head>
<body>
    <h1>Customer Support Chat</h1>

    {% webchat_component
        theme="light"
        primary_color="#007bff"
        max_messages=100
        auto_refresh=3
    %}
</body>
</html>
```

---

## 6. Auto-Refresh Mechanism

### 6.1 Polling Implementation
Since Phase 2 doesn't include WebSockets, implement simple polling:

```javascript
_startAutoRefresh() {
  if (this.autoRefresh <= 0) return;

  this._refreshInterval = setInterval(async () => {
    if (!document.hidden) { // Only refresh if page is visible
      await this._refreshMessages();
    }
  }, this.autoRefresh * 1000);
}

_stopAutoRefresh() {
  if (this._refreshInterval) {
    clearInterval(this._refreshInterval);
    this._refreshInterval = null;
  }
}

async _refreshMessages() {
  try {
    const lastMessageId = this.messages[this.messages.length - 1]?.id;
    const data = await this.api.getMessages(this.chatId, this.maxMessages, null, lastMessageId);

    if (data.messages.length > 0) {
      // New messages arrived
      this.messages = [...this.messages, ...data.messages];
      this._scrollToBottom();
    }
  } catch (error) {
    console.error('Refresh failed:', error);
  }
}
```

---

## 7. Media Upload Support

### 7.1 Update Backend API
**File**: `unicom/views/webchat_views.py`

**Update send_message_api to handle file uploads**:
```python
def send_webchat_message_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    text = request.POST.get('text', '').strip()
    chat_id = request.POST.get('chat_id')
    media_file = request.FILES.get('media')

    # Determine media type
    media_type = 'text'
    if media_file:
        content_type = media_file.content_type
        if content_type.startswith('image/'):
            media_type = 'image'
        elif content_type.startswith('audio/'):
            media_type = 'audio'

    message_data = {
        'text': text or f'**{media_type.title()}**',
        'chat_id': chat_id,
        'media_type': media_type,
        'file': media_file,
    }

    # ... rest of implementation
```

### 7.2 Update save_webchat_message
Handle file uploads similar to save_telegram_message:
```python
def save_webchat_message(channel, message_data, request, user=None):
    # ... existing code ...

    # Handle media file
    media_file = message_data.get('file')
    if media_file:
        message.media.save(media_file.name, media_file, save=True)

    return message
```

### 7.3 Media URLs in API Response
Ensure `media_url` is included in message serialization:
```python
{
    'id': message.id,
    'text': message.text,
    # ...
    'media_type': message.media_type,
    'media_url': message.media.url if message.media else None,
}
```

---

## 8. Responsive Design

### 8.1 Mobile Support
Add responsive CSS:
```css
@media (max-width: 768px) {
  .unicom-chat-container {
    height: 100vh;
    max-width: 100%;
    border-radius: 0;
    border: none;
  }

  .message-bubble {
    max-width: 85%;
  }
}
```

### 8.2 Touch-Friendly UI
- Larger tap targets (minimum 44px)
- Swipe gestures (optional for Phase 2, can defer to Phase 5)

---

## Phase 2 Deliverables - What Should Work:

### ✅ UI Component
1. **LitElement Component**: Fully functional `<unicom-chat>` custom element
2. **Easy Integration**: Drop into any Django template with single template tag
3. **Customizable**: CSS custom properties for colors, fonts, layout
4. **Theme Support**: Pre-built light/dark themes

### ✅ Message Display
1. **Message List**: Scrollable, auto-scroll to bottom
2. **Media Support**: Display images and audio messages
3. **Rich Content**: Support for HTML messages
4. **Pagination**: "Load More" button for message history
5. **Timestamps**: Formatted display of message times
6. **Sender Display**: Show sender names for incoming messages

### ✅ Message Input
1. **Text Input**: Multi-line textarea with auto-expand
2. **Send Button**: Click or Enter to send
3. **Media Upload**: Image and audio file uploads
4. **File Preview**: Preview before sending
5. **Validation**: Disable send when empty

### ✅ Auto-Refresh
1. **Polling**: Configurable auto-refresh interval
2. **Smart Refresh**: Only poll when page is visible
3. **New Message Detection**: Fetch only new messages

### ✅ User Experience
1. **Loading States**: Spinners and disabled states
2. **Error Handling**: Display API errors to user
3. **Responsive**: Works on mobile and desktop
4. **Accessibility**: Semantic HTML, keyboard navigation

### ⚠️ Known Limitations (to be addressed in later phases)
- No WebSocket/real-time push notifications
- No typing indicators
- No read receipts
- Single chat only (multi-chat in Phase 3)
- No voice recording (file upload only)
- No emoji picker
- No message search

---

## Success Criteria

Phase 2 is complete when:

1. ✅ Component loads without errors in browser
2. ✅ User can type and send text messages
3. ✅ User can upload and send images
4. ✅ User can upload and send audio files
5. ✅ Messages display correctly (text, images, audio)
6. ✅ Incoming vs outgoing messages styled differently
7. ✅ Auto-refresh fetches new messages
8. ✅ "Load More" loads message history
9. ✅ Component is themeable via CSS custom properties
10. ✅ Component works on mobile devices
11. ✅ Can be embedded in any Django template via `{% webchat_component %}`
