/**
 * Chat List Component
 * Displays list of chats in a sidebar
 */
import { LitElement, html, css } from 'lit';
import { formatRelativeTime } from '../utils/datetime-formatter.js';

export class ChatList extends LitElement {
  static properties = {
    chats: { type: Array },
    selectedChatId: { type: String, attribute: 'selected-chat-id' },
    loading: { type: Boolean },
  };

  static styles = css`
    :host {
      display: block;
      height: 100%;
      background: var(--background-color, #ffffff);
      border-right: 1px solid var(--border-color, #dee2e6);
    }

    .chat-list-container {
      display: flex;
      flex-direction: column;
      height: 100%;
    }

    .chat-list-header {
      padding: 16px;
      border-bottom: 1px solid var(--border-color, #dee2e6);
      background: var(--primary-color, #007bff);
      color: white;
    }

    .chat-list-header h3 {
      margin: 0;
      font-size: 1.1em;
      font-weight: 600;
    }

    .new-chat-btn {
      margin-top: 12px;
      width: 100%;
      padding: 10px;
      background: white;
      color: var(--primary-color, #007bff);
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
      transition: opacity 0.2s;
    }

    .new-chat-btn:hover {
      opacity: 0.9;
    }

    .chat-list-items {
      flex: 1;
      overflow-y: auto;
    }

    .chat-item {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border-color, #dee2e6);
      cursor: pointer;
      transition: background 0.2s;
    }

    .chat-item:hover {
      background: rgba(0, 0, 0, 0.03);
    }

    .chat-item.selected {
      background: var(--primary-color, #007bff);
      color: white;
    }

    .chat-item.selected .chat-preview,
    .chat-item.selected .chat-time {
      color: rgba(255, 255, 255, 0.8);
    }

    .chat-name {
      font-weight: 600;
      margin-bottom: 4px;
      font-size: 0.95em;
    }

    .chat-preview {
      font-size: 0.85em;
      color: var(--secondary-color, #6c757d);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-bottom: 4px;
    }

    .chat-time {
      font-size: 0.75em;
      color: var(--secondary-color, #6c757d);
    }

    .loading-spinner {
      padding: 20px;
      text-align: center;
      color: var(--secondary-color, #6c757d);
    }

    .empty-state {
      padding: 40px 20px;
      text-align: center;
      color: var(--secondary-color, #6c757d);
    }

    .empty-state-icon {
      font-size: 2em;
      margin-bottom: 12px;
      opacity: 0.5;
    }

    .dark {
      --background-color: #2d2d2d;
      --border-color: #444;
      --secondary-color: #aaa;
    }
  `;

  constructor() {
    super();
    this.chats = [];
    this.selectedChatId = null;
    this.loading = false;
  }

  _handleChatClick(chat) {
    this.dispatchEvent(new CustomEvent('chat-selected', {
      detail: { chatId: chat.id },
      bubbles: true,
      composed: true,
    }));
  }

  _handleNewChat() {
    this.dispatchEvent(new CustomEvent('new-chat', {
      bubbles: true,
      composed: true,
    }));
  }

  _formatTime(timestamp) {
    if (!timestamp) return '';
    return formatRelativeTime(timestamp);
  }

  render() {
    return html`
      <div class="chat-list-container">
        <div class="chat-list-header">
          <h3>Chats</h3>
          <button class="new-chat-btn" @click=${this._handleNewChat}>
            + New Chat
          </button>
        </div>

        <div class="chat-list-items">
          ${this.loading ? html`
            <div class="loading-spinner">Loading chats...</div>
          ` : ''}

          ${!this.loading && this.chats.length === 0 ? html`
            <div class="empty-state">
              <div class="empty-state-icon">💬</div>
              <div>No chats yet.<br>Click "New Chat" to start!</div>
            </div>
          ` : ''}

          ${this.chats.map(chat => html`
            <div
              class="chat-item ${chat.id === this.selectedChatId ? 'selected' : ''}"
              @click=${() => this._handleChatClick(chat)}>
              <div class="chat-name">${chat.name || 'Chat ' + chat.id}</div>
              ${chat.last_message ? html`
                <div class="chat-preview">${chat.last_message.text || 'Media message'}</div>
                <div class="chat-time">${this._formatTime(chat.last_message.timestamp)}</div>
              ` : html`
                <div class="chat-preview">No messages yet</div>
              `}
            </div>
          `)}
        </div>
      </div>
    `;
  }
}

customElements.define('chat-list', ChatList);
