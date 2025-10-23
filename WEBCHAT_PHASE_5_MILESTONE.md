# WebChat Implementation - Phase 5: Advanced Features & Polish

**Goal**: Add production-ready features including rich media support, accessibility, advanced UI features, and optimization.

**Prerequisites**: Phases 1-4 must be complete (full real-time chat system functional)

---

## 1. Rich Media Enhancements

### 1.1 Voice Recording
**Browser API**: MediaRecorder API

**File**: `unicom/static/unicom/webchat/components/voice-recorder.js`

```javascript
import { LitElement, html, css } from 'lit';

export class VoiceRecorder extends LitElement {
  static properties = {
    recording: { type: Boolean, state: true },
    recordingTime: { type: Number, state: true },
  };

  constructor() {
    super();
    this.recording = false;
    this.recordingTime = 0;
    this.mediaRecorder = null;
    this.audioChunks = [];
  }

  render() {
    return html`
      <div class="voice-recorder">
        ${!this.recording ? html`
          <button @click=${this.startRecording} class="record-btn">
            🎤 Record Voice
          </button>
        ` : html`
          <div class="recording-controls">
            <span class="recording-indicator">🔴 Recording... ${this._formatTime(this.recordingTime)}</span>
            <button @click=${this.stopRecording} class="stop-btn">Stop</button>
            <button @click=${this.cancelRecording} class="cancel-btn">Cancel</button>
          </div>
        `}
      </div>
    `;
  }

  async startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      this.mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });

      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        this.audioChunks.push(event.data);
      };

      this.mediaRecorder.onstop = () => {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        this._sendAudio(audioBlob);

        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };

      this.mediaRecorder.start();
      this.recording = true;

      // Update recording time
      this._startTimer();

    } catch (error) {
      console.error('Microphone access denied:', error);
      alert('Please allow microphone access to record voice messages');
    }
  }

  stopRecording() {
    if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
      this.mediaRecorder.stop();
      this.recording = false;
      this._stopTimer();
    }
  }

  cancelRecording() {
    if (this.mediaRecorder) {
      this.mediaRecorder.stop();
      this.audioChunks = []; // Discard recording
      this.recording = false;
      this._stopTimer();
    }
  }

  _startTimer() {
    this.recordingTime = 0;
    this.timerInterval = setInterval(() => {
      this.recordingTime++;
      // Auto-stop after 5 minutes
      if (this.recordingTime >= 300) {
        this.stopRecording();
      }
    }, 1000);
  }

  _stopTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
    this.recordingTime = 0;
  }

  _sendAudio(blob) {
    // Create File from Blob
    const file = new File([blob], 'voice_message.webm', { type: 'audio/webm' });

    this.dispatchEvent(new CustomEvent('voice-recorded', {
      detail: { file }
    }));
  }

  _formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
}

customElements.define('voice-recorder', VoiceRecorder);
```

**Integration in message-input.js**:
```javascript
render() {
  return html`
    <div class="message-input-container">
      <!-- ... existing code ... -->

      <voice-recorder
        @voice-recorded=${this._handleVoiceRecorded}>
      </voice-recorder>

      <!-- ... rest of input ... -->
    </div>
  `;
}

async _handleVoiceRecorded(e) {
  const { file } = e.detail;
  await this._sendMedia(file, 'Voice message');
}
```

### 1.2 Image Editor
**Features**:
- Crop/rotate images before sending
- Add text captions
- Simple filters (optional)

**File**: `unicom/static/unicom/webchat/components/image-editor.js`

```javascript
export class ImageEditor extends LitElement {
  static properties = {
    imageFile: { type: Object },
    imageUrl: { type: String, state: true },
    caption: { type: String, state: true },
  };

  render() {
    if (!this.imageUrl) return html``;

    return html`
      <div class="image-editor-modal">
        <div class="editor-content">
          <img src="${this.imageUrl}" alt="Preview">

          <input
            type="text"
            class="caption-input"
            placeholder="Add a caption..."
            .value=${this.caption}
            @input=${(e) => this.caption = e.target.value}>

          <div class="editor-actions">
            <button @click=${this._handleSend}>Send</button>
            <button @click=${this._handleCancel}>Cancel</button>
          </div>
        </div>
      </div>
    `;
  }

  _handleSend() {
    this.dispatchEvent(new CustomEvent('send-image', {
      detail: {
        file: this.imageFile,
        caption: this.caption
      }
    }));
    this._close();
  }

  _handleCancel() {
    this._close();
  }

  _close() {
    this.imageFile = null;
    this.imageUrl = null;
    this.caption = '';
  }
}
```

### 1.3 File Upload Progress
Show upload progress for large files:

```javascript
async _uploadFile(file) {
  const formData = new FormData();
  formData.append('media', file);
  formData.append('chat_id', this.chatId);

  const xhr = new XMLHttpRequest();

  xhr.upload.addEventListener('progress', (e) => {
    if (e.lengthComputable) {
      const percentComplete = (e.loaded / e.total) * 100;
      this._updateUploadProgress(percentComplete);
    }
  });

  return new Promise((resolve, reject) => {
    xhr.onload = () => {
      if (xhr.status === 200) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error('Upload failed'));
      }
    };

    xhr.onerror = () => reject(new Error('Upload failed'));

    xhr.open('POST', `${this.apiBase}/send/`);
    xhr.setRequestHeader('X-CSRFToken', this._getCSRFToken());
    xhr.send(formData);
  });
}
```

---

## 2. Message Features

### 2.1 Message Editing
**Backend**: Add edit endpoint

**File**: `unicom/views/webchat_views.py`

```python
@require_http_methods(["PATCH"])
def edit_message_api(request, message_id):
    """Edit message text (only within 15 minutes of sending)."""
    from unicom.models import Message
    from django.utils import timezone
    from datetime import timedelta

    try:
        message = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)

    # Verify sender
    account = get_or_create_account(message.channel, request)
    if message.sender != account:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    # Check if message is within edit window (15 minutes)
    if timezone.now() - message.timestamp > timedelta(minutes=15):
        return JsonResponse({'error': 'Edit time expired'}, status=400)

    # Update message
    new_text = request.POST.get('text', '').strip()
    if not new_text:
        return JsonResponse({'error': 'Text required'}, status=400)

    message.text = new_text
    message.save(update_fields=['text'])

    # Broadcast update via WebSocket
    _broadcast_message_edit(message)

    return JsonResponse({
        'success': True,
        'message': {
            'id': message.id,
            'text': message.text
        }
    })
```

**Frontend**: Add edit UI

```javascript
_handleEditMessage(messageId, newText) {
  // Send edit request
  // Update message in list
  // Show "edited" badge
}
```

### 2.2 Message Deletion
**Backend**: Soft delete messages

```python
@require_http_methods(["DELETE"])
def delete_message_api(request, message_id):
    """Soft delete message (only sender can delete)."""
    # Verify ownership
    # Set message.text = "Message deleted"
    # Broadcast deletion
    # Return success
```

### 2.3 Message Reactions
**Backend**: Store reactions in JSON field or separate model

```python
# Add to Message model
reactions = models.JSONField(default=dict)  # {"👍": ["user1", "user2"], "❤️": ["user3"]}

# API endpoint
@require_http_methods(["POST"])
def react_to_message_api(request, message_id):
    emoji = request.POST.get('emoji')
    # Add/remove reaction
    # Broadcast update
```

**Frontend**: Reaction picker and display

```javascript
<div class="message-reactions">
  ${Object.entries(message.reactions || {}).map(([emoji, users]) => html`
    <button
      class="reaction ${users.includes(currentUserId) ? 'active' : ''}"
      @click=${() => this._toggleReaction(message.id, emoji)}>
      ${emoji} ${users.length}
    </button>
  `)}
  <button class="add-reaction" @click=${() => this._showReactionPicker(message.id)}>
    ➕
  </button>
</div>
```

### 2.4 Message Search
**Backend**: Full-text search in messages

```python
@require_http_methods(["GET"])
def search_messages_api(request):
    query = request.GET.get('q', '').strip()
    chat_id = request.GET.get('chat_id')

    if not query:
        return JsonResponse({'error': 'Query required'}, status=400)

    # Get account and verify access
    account = get_or_create_account(get_webchat_channel(), request)

    from unicom.models import Message, AccountChat

    # Build query
    messages = Message.objects.filter(
        chat__accountchat__account=account,
        text__icontains=query
    )

    if chat_id:
        messages = messages.filter(chat_id=chat_id)

    messages = messages.order_by('-timestamp')[:50]

    # Serialize results
    results = [{
        'id': msg.id,
        'text': msg.text,
        'chat_id': msg.chat_id,
        'timestamp': msg.timestamp.isoformat(),
        # ... other fields
    } for msg in messages]

    return JsonResponse({
        'success': True,
        'results': results
    })
```

**Frontend**: Search UI in sidebar

```javascript
<input
  type="search"
  class="message-search"
  placeholder="Search in messages..."
  @input=${this._handleMessageSearch}>

<div class="search-results">
  ${this.searchResults.map(msg => html`
    <div class="search-result" @click=${() => this._jumpToMessage(msg.id)}>
      <div class="result-text">${this._highlightQuery(msg.text)}</div>
      <div class="result-chat">${this._getChatName(msg.chat_id)}</div>
    </div>
  `)}
</div>
```

---

## 3. Accessibility (A11y)

### 3.1 Keyboard Navigation
**Features**:
- Tab through messages, input, buttons
- Arrow keys to navigate message list
- Shortcuts: Ctrl+N for new chat, Escape to close modals

```javascript
connectedCallback() {
  super.connectedCallback();
  this.addEventListener('keydown', this._handleKeyDown);
}

_handleKeyDown(e) {
  // Ctrl+N: New chat
  if (e.ctrlKey && e.key === 'n') {
    e.preventDefault();
    this._handleNewChat();
  }

  // Escape: Close modals
  if (e.key === 'Escape') {
    this._closeModals();
  }

  // Arrow up/down: Navigate messages
  if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    this._navigateMessages(e.key === 'ArrowUp' ? -1 : 1);
  }
}
```

### 3.2 Screen Reader Support
**ARIA labels and roles**:

```javascript
render() {
  return html`
    <div
      class="unicom-chat-container"
      role="application"
      aria-label="Chat interface">

      <chat-sidebar
        role="navigation"
        aria-label="Chat list">
        <!-- Chats -->
      </chat-sidebar>

      <div class="chat-main" role="main">
        <div
          class="message-list"
          role="log"
          aria-live="polite"
          aria-label="Message history">
          <!-- Messages -->
        </div>

        <div
          class="message-input"
          role="region"
          aria-label="Message composition">
          <textarea aria-label="Type your message"></textarea>
          <button aria-label="Send message">Send</button>
        </div>
      </div>
    </div>
  `;
}
```

### 3.3 Focus Management
```javascript
// Focus input after sending message
_handleSendMessage() {
  // ... send logic ...
  this.shadowRoot.querySelector('textarea').focus();
}

// Announce new messages to screen readers
_handleIncomingMessage(message) {
  this.messages = [...this.messages, message];

  // Create live region announcement
  const announcement = document.createElement('div');
  announcement.setAttribute('role', 'status');
  announcement.setAttribute('aria-live', 'polite');
  announcement.textContent = `New message from ${message.sender_name}: ${message.text}`;
  announcement.style.position = 'absolute';
  announcement.style.left = '-10000px';

  this.shadowRoot.appendChild(announcement);

  setTimeout(() => announcement.remove(), 1000);
}
```

---

## 4. Performance Optimization

### 4.1 Virtual Scrolling
For very long message lists:

```javascript
import { VirtualScroller } from '@lit-labs/virtualizer';

render() {
  return html`
    <lit-virtualizer
      .items=${this.messages}
      .renderItem=${(msg) => html`<message-item .message=${msg}></message-item>`}
      .scrollTarget=${window}>
    </lit-virtualizer>
  `;
}
```

### 4.2 Image Lazy Loading
```javascript
<img
  src="${message.media_url}"
  loading="lazy"
  decoding="async"
  alt="${message.text}">
```

### 4.3 Message Pagination
Load messages in chunks:

```javascript
async _loadMoreMessages() {
  const oldestMessage = this.messages[0];
  const data = await this.api.getMessages(
    this.chatId,
    50,
    oldestMessage.id // before cursor
  );

  // Prepend older messages
  this.messages = [...data.messages.reverse(), ...this.messages];
}
```

### 4.4 Debounce Typing Indicators
```javascript
import { debounce } from './utils/debounce.js';

constructor() {
  super();
  this._debouncedTyping = debounce(() => {
    this._sendTypingIndicator(false);
  }, 2000);
}

_handleInput(e) {
  this._sendTypingIndicator(true);
  this._debouncedTyping();
}
```

---

## 5. Advanced UI Features

### 5.1 Emoji Picker
**Library**: emoji-picker-element

```bash
npm install emoji-picker-element
```

```javascript
import 'emoji-picker-element';

render() {
  return html`
    <div class="emoji-picker-container">
      <button @click=${this._toggleEmojiPicker}>😀</button>

      ${this.showEmojiPicker ? html`
        <emoji-picker
          @emoji-click=${this._handleEmojiSelect}>
        </emoji-picker>
      ` : ''}
    </div>
  `;
}

_handleEmojiSelect(e) {
  const emoji = e.detail.unicode;
  this.inputText += emoji;
  this.showEmojiPicker = false;
}
```

### 5.2 Markdown Support
**Library**: marked.js

```javascript
import { marked } from 'marked';
import DOMPurify from 'dompurify';

_renderMessageText(text) {
  // Parse markdown and sanitize HTML
  const html = marked.parse(text);
  const clean = DOMPurify.sanitize(html);
  return unsafeHTML(clean);
}
```

### 5.3 Code Syntax Highlighting
**Library**: highlight.js

```javascript
import hljs from 'highlight.js';

_renderCodeBlock(code, language) {
  const highlighted = hljs.highlight(code, { language }).value;
  return html`
    <pre><code class="hljs ${language}">${unsafeHTML(highlighted)}</code></pre>
  `;
}
```

### 5.4 Link Previews
**Backend**: Fetch OpenGraph metadata

```python
@require_http_methods(["GET"])
def link_preview_api(request):
    url = request.GET.get('url')

    # Fetch URL and parse OpenGraph tags
    # Return title, description, image

    return JsonResponse({
        'success': True,
        'preview': {
            'title': '...',
            'description': '...',
            'image': '...',
            'url': url
        }
    })
```

**Frontend**: Show rich previews for links

```javascript
_detectLinks(text) {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const urls = text.match(urlRegex);

  if (urls) {
    urls.forEach(url => this._fetchLinkPreview(url));
  }
}

async _fetchLinkPreview(url) {
  const data = await this.api.getLinkPreview(url);
  // Display rich preview card
}
```

---

## 6. Mobile Enhancements

### 6.1 Pull-to-Refresh
```javascript
_handleTouchStart(e) {
  this.touchStartY = e.touches[0].clientY;
}

_handleTouchMove(e) {
  const touchY = e.touches[0].clientY;
  const scrollTop = this.messageListEl.scrollTop;

  if (scrollTop === 0 && touchY > this.touchStartY) {
    // Pulled down at top of list
    this._showRefreshIndicator();
  }
}

_handleTouchEnd() {
  if (this.isRefreshing) {
    this._loadMoreMessages();
  }
}
```

### 6.2 Swipe Gestures
- Swipe left on chat: Archive/delete
- Swipe right on message: Reply/quote

```javascript
import Hammer from 'hammerjs';

connectedCallback() {
  super.connectedCallback();

  const hammer = new Hammer(this.shadowRoot.querySelector('.chat-list'));

  hammer.on('swipeleft', (e) => {
    const chatItem = e.target.closest('.chat-item');
    if (chatItem) {
      this._showChatActions(chatItem);
    }
  });
}
```

### 6.3 Mobile Keyboard Handling
```javascript
// Resize chat when keyboard opens
window.visualViewport.addEventListener('resize', () => {
  this._adjustLayoutForKeyboard();
});

_adjustLayoutForKeyboard() {
  const viewport = window.visualViewport;
  this.style.height = `${viewport.height}px`;
}
```

---

## 7. Theme System

### 7.1 Advanced Theme Editor
**UI for customizing all CSS properties**:

```javascript
<theme-editor
  @theme-change=${this._handleThemeChange}>
</theme-editor>
```

### 7.2 Dark Mode Auto-Detection
```javascript
connectedCallback() {
  super.connectedCallback();

  // Detect system theme preference
  if (window.matchMedia) {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');

    if (prefersDark.matches && !this.theme) {
      this.theme = 'dark';
    }

    // Listen for changes
    prefersDark.addEventListener('change', (e) => {
      this.theme = e.matches ? 'dark' : 'light';
    });
  }
}
```

### 7.3 Custom Theme Presets
```javascript
export const themePresets = {
  light: { /* ... */ },
  dark: { /* ... */ },
  blue: {
    '--unicom-primary-color': '#0066cc',
    '--unicom-message-bg-outgoing': '#0066cc',
    // ...
  },
  green: {
    '--unicom-primary-color': '#25D366', // WhatsApp green
    // ...
  },
  purple: {
    '--unicom-primary-color': '#7B68EE',
    // ...
  }
};
```

---

## 8. Analytics & Monitoring

### 8.1 Usage Analytics
Track:
- Messages sent/received
- Active users
- Average response time
- Popular features

```python
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta

def get_webchat_analytics(start_date, end_date):
    messages = Message.objects.filter(
        platform='WebChat',
        timestamp__gte=start_date,
        timestamp__lte=end_date
    )

    return {
        'total_messages': messages.count(),
        'incoming': messages.filter(is_outgoing=False).count(),
        'outgoing': messages.filter(is_outgoing=True).count(),
        'active_users': messages.values('sender').distinct().count(),
        'avg_response_time': calculate_avg_response_time(messages),
    }
```

### 8.2 Error Tracking
**Frontend**: Send errors to backend

```javascript
window.addEventListener('error', (e) => {
  this._reportError({
    message: e.message,
    stack: e.error?.stack,
    url: window.location.href
  });
});

async _reportError(error) {
  try {
    await fetch('/unicom/webchat/report-error/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(error)
    });
  } catch (e) {
    // Silent fail
  }
}
```

---

## Phase 5 Deliverables - What Should Work:

### ✅ Rich Media
1. **Voice Recording**: In-browser voice message recording
2. **Image Editor**: Crop and caption images before sending
3. **File Upload Progress**: Visual progress for large files
4. **Media Galleries**: Swipeable image galleries

### ✅ Message Features
1. **Edit Messages**: Edit within 15-minute window
2. **Delete Messages**: Soft delete with "Message deleted" placeholder
3. **Message Reactions**: Emoji reactions with picker
4. **Message Search**: Full-text search across all messages
5. **Quote Reply**: Reply with quoted message
6. **Forward Messages**: Forward to other chats

### ✅ Accessibility
1. **Keyboard Navigation**: Full keyboard support with shortcuts
2. **Screen Readers**: Proper ARIA labels and live regions
3. **Focus Management**: Logical focus flow
4. **High Contrast**: Support for high contrast mode

### ✅ Performance
1. **Virtual Scrolling**: Smooth scrolling with thousands of messages
2. **Lazy Loading**: Images and old messages load on demand
3. **Optimized Rendering**: Efficient re-renders with Lit
4. **Debounced Actions**: Smart throttling of network requests

### ✅ Advanced UI
1. **Emoji Picker**: Rich emoji selection
2. **Markdown Support**: Formatted text with markdown
3. **Code Highlighting**: Syntax highlighted code blocks
4. **Link Previews**: Rich previews for shared links

### ✅ Mobile
1. **Pull-to-Refresh**: Natural pull gesture to load more
2. **Swipe Gestures**: Intuitive swipe actions
3. **Keyboard Handling**: Smart layout adjustment for mobile keyboards
4. **Touch Optimized**: Larger tap targets and smooth scrolling

### ✅ Theming
1. **Theme Editor**: Visual theme customization
2. **Auto Dark Mode**: Respect system preferences
3. **Multiple Presets**: Several built-in themes
4. **Theme Persistence**: Remember user's theme choice

### ✅ Production Ready
1. **Error Tracking**: Automatic error reporting
2. **Analytics**: Usage metrics and insights
3. **Logging**: Comprehensive logging for debugging
4. **Documentation**: Complete API and component docs

---

## Success Criteria

Phase 5 is complete when:

1. ✅ Voice messages can be recorded and sent
2. ✅ Images can be edited before sending
3. ✅ Messages can be edited and deleted
4. ✅ Emoji reactions work smoothly
5. ✅ Full-text search finds messages instantly
6. ✅ Component is fully keyboard accessible
7. ✅ Screen readers announce all interactions
8. ✅ Performance is smooth with 1000+ messages
9. ✅ Emoji picker inserts emojis correctly
10. ✅ Markdown renders properly with syntax highlighting
11. ✅ Link previews show for shared URLs
12. ✅ Mobile gestures work intuitively
13. ✅ Dark mode auto-switches with system
14. ✅ All errors are tracked and logged
15. ✅ Component meets WCAG 2.1 AA standards

---

## Post-Phase 5: Future Enhancements

### Potential Future Features
- **Video Messages**: Record and send short video clips
- **Screen Sharing**: Share screen during support chats
- **Chat Folders**: Organize chats into custom folders
- **Message Pinning**: Pin important messages to top
- **Chat Export**: Export chat history as PDF/JSON
- **Multi-language**: i18n support for multiple languages
- **Custom Stickers**: Upload and send custom sticker packs
- **Message Templates**: Quick reply templates for common responses
- **Chatbots**: AI-powered automated responses
- **Voice/Video Calls**: Real-time audio/video communication

---

## Production Deployment Checklist

### Backend
- [ ] Configure HTTPS for WebSocket (wss://)
- [ ] Set up Redis for Channel Layer
- [ ] Configure Django Channels with Daphne/Uvicorn
- [ ] Set up database indexes for performance
- [ ] Configure media storage (S3/CDN)
- [ ] Set up backup strategy
- [ ] Configure logging and monitoring
- [ ] Set up error tracking (Sentry)
- [ ] Load testing for WebSocket connections
- [ ] Security audit (OWASP)

### Frontend
- [ ] Minify and bundle JavaScript
- [ ] Optimize images and assets
- [ ] Set up CDN for static files
- [ ] Configure service worker (PWA)
- [ ] Browser compatibility testing
- [ ] Performance testing (Lighthouse)
- [ ] Accessibility audit (aXe, WAVE)
- [ ] Cross-browser testing
- [ ] Mobile device testing
- [ ] Load testing with realistic data

### DevOps
- [ ] Set up CI/CD pipeline
- [ ] Configure auto-scaling
- [ ] Set up health checks
- [ ] Configure rate limiting
- [ ] Set up DDoS protection
- [ ] Configure SSL certificates
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure alerting
- [ ] Document deployment process
- [ ] Create rollback procedures

---

**🎉 Congratulations! With Phase 5 complete, you have a production-ready, feature-rich WebChat system integrated into unicom!**
