/**
 * Main WebChat Component
 * Entry point for the unicom-chat custom element
 */
import { LitElement, html, css } from 'lit';
import { baseStyles } from './webchat-styles.js';
import { WebChatAPI } from './utils/api-client.js';
import './components/message-list.js';
import './components/message-input.js';

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
    hasMore: { type: Boolean, state: true },
  };

  static styles = [baseStyles];

  constructor() {
    super();
    this.apiBase = '/unicom/webchat';
    this.chatId = null;
    this.channelId = null;
    this.maxMessages = 50;
    this.theme = 'light';
    this.autoRefresh = 5;

    this.messages = [];
    this.loading = false;
    this.sending = false;
    this.error = null;
    this.hasMore = false;

    this.api = null;
    this._refreshInterval = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.api = new WebChatAPI(this.apiBase);
    this.loadMessages();

    if (this.autoRefresh > 0) {
      this._startAutoRefresh();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._stopAutoRefresh();
  }

  /**
   * Load initial messages
   */
  async loadMessages() {
    this.loading = true;
    this.error = null;

    try {
      const data = await this.api.getMessages(this.chatId, this.maxMessages);
      this.messages = data.messages || [];
      this.hasMore = data.has_more || false;

      // If a chat was created, store the chat_id
      if (data.chat_id && !this.chatId) {
        this.chatId = data.chat_id;
      }
    } catch (err) {
      this.error = err.message;
      console.error('Failed to load messages:', err);
    } finally {
      this.loading = false;
    }
  }

  /**
   * Load more (older) messages
   */
  async _handleLoadMore() {
    if (this.loading || !this.hasMore || this.messages.length === 0) return;

    this.loading = true;
    this.error = null;

    try {
      const oldestMessage = this.messages[0];
      const data = await this.api.getMessages(
        this.chatId,
        this.maxMessages,
        oldestMessage.id
      );

      // Prepend older messages
      this.messages = [...(data.messages || []), ...this.messages];
      this.hasMore = data.has_more || false;
    } catch (err) {
      this.error = err.message;
      console.error('Failed to load more messages:', err);
    } finally {
      this.loading = false;
    }
  }

  /**
   * Send a message
   */
  async _handleSendMessage(e) {
    const { text, file } = e.detail;

    if (this.sending) return;
    if (!text && !file) return;

    this.sending = true;
    this.error = null;

    try {
      const response = await this.api.sendMessage(text, this.chatId, file);

      // Update chat_id if this was the first message
      if (response.chat_id && !this.chatId) {
        this.chatId = response.chat_id;
      }

      // Add the sent message to the list
      if (response.message) {
        this.messages = [...this.messages, response.message];
      }

      // Trigger a refresh to get bot response
      setTimeout(() => this._refreshMessages(), 500);
    } catch (err) {
      this.error = err.message;
      console.error('Failed to send message:', err);
    } finally {
      this.sending = false;
    }
  }

  /**
   * Start auto-refresh timer
   */
  _startAutoRefresh() {
    if (this.autoRefresh <= 0) return;

    this._refreshInterval = setInterval(() => {
      // Only refresh if page is visible
      if (!document.hidden) {
        this._refreshMessages();
      }
    }, this.autoRefresh * 1000);
  }

  /**
   * Stop auto-refresh timer
   */
  _stopAutoRefresh() {
    if (this._refreshInterval) {
      clearInterval(this._refreshInterval);
      this._refreshInterval = null;
    }
  }

  /**
   * Refresh to get new messages
   */
  async _refreshMessages() {
    if (this.loading || this.sending) return;

    try {
      const lastMessage = this.messages[this.messages.length - 1];
      const afterId = lastMessage ? lastMessage.id : null;

      const data = await this.api.getMessages(
        this.chatId,
        this.maxMessages,
        null,
        afterId
      );

      if (data.messages && data.messages.length > 0) {
        // Append new messages
        this.messages = [...this.messages, ...data.messages];
      }
    } catch (err) {
      // Silent fail for refresh errors
      console.error('Refresh failed:', err);
    }
  }

  render() {
    return html`
      <div class="unicom-chat-container ${this.theme}">
        ${this.error ? html`
          <div class="error-banner">${this.error}</div>
        ` : ''}

        <message-list
          .messages=${this.messages}
          .loading=${this.loading}
          .hasMore=${this.hasMore}
          @load-more=${this._handleLoadMore}>
        </message-list>

        <message-input
          .disabled=${this.sending}
          @send-message=${this._handleSendMessage}>
        </message-input>
      </div>
    `;
  }
}

customElements.define('unicom-chat', UnicomChat);
