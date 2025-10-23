/**
 * WebChat Component with Sidebar
 * Multi-chat support with chat list sidebar
 */
import { LitElement, html, css } from 'lit';
import { baseStyles } from './webchat-styles.js';
import { WebChatAPI } from './utils/api-client.js';
import './components/chat-list.js';
import './components/message-list.js';
import './components/message-input.js';

export class UnicomChatWithSidebar extends LitElement {
  static properties = {
    apiBase: { type: String, attribute: 'api-base' },
    channelId: { type: Number, attribute: 'channel-id' },
    maxMessages: { type: Number, attribute: 'max-messages' },
    theme: { type: String },
    autoRefresh: { type: Number, attribute: 'auto-refresh' },

    // Internal state
    chats: { type: Array, state: true },
    currentChatId: { type: String, state: true },
    messages: { type: Array, state: true },
    loading: { type: Boolean, state: true },
    loadingChats: { type: Boolean, state: true },
    sending: { type: Boolean, state: true },
    error: { type: String, state: true },
    hasMore: { type: Boolean, state: true },
  };

  static styles = [
    baseStyles,
    css`
      .chat-with-sidebar-container {
        display: flex;
        height: 100%;
      }

      .sidebar {
        width: 300px;
        min-width: 300px;
        height: 100%;
      }

      .chat-main {
        flex: 1;
        display: flex;
        flex-direction: column;
        height: 100%;
      }

      @media (max-width: 768px) {
        .sidebar {
          width: 100%;
          position: absolute;
          z-index: 1000;
          height: 100%;
        }

        .sidebar.hidden {
          display: none;
        }

        .mobile-back-btn {
          display: block;
          padding: 12px 16px;
          background: var(--primary-color);
          color: white;
          border: none;
          border-bottom: 1px solid var(--border-color);
          cursor: pointer;
          width: 100%;
          text-align: left;
          font-size: 1em;
        }
      }

      @media (min-width: 769px) {
        .mobile-back-btn {
          display: none;
        }
      }
    `
  ];

  constructor() {
    super();
    this.apiBase = '/unicom/webchat';
    this.channelId = null;
    this.maxMessages = 50;
    this.theme = 'light';
    this.autoRefresh = 5;

    this.chats = [];
    this.currentChatId = null;
    this.messages = [];
    this.loading = false;
    this.loadingChats = false;
    this.sending = false;
    this.error = null;
    this.hasMore = false;

    this.api = null;
    this._refreshInterval = null;
    this._showSidebar = true;
  }

  connectedCallback() {
    super.connectedCallback();
    this.api = new WebChatAPI(this.apiBase);
    this.loadChats();

    if (this.autoRefresh > 0) {
      this._startAutoRefresh();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._stopAutoRefresh();
  }

  /**
   * Load list of chats
   */
  async loadChats() {
    this.loadingChats = true;

    try {
      const data = await this.api.getChats();
      this.chats = data.chats || [];

      // If no chat selected, select the first one
      if (!this.currentChatId && this.chats.length > 0) {
        this.currentChatId = this.chats[0].id;
        await this.loadMessages();
      }
    } catch (err) {
      this.error = err.message;
      console.error('Failed to load chats:', err);
    } finally {
      this.loadingChats = false;
    }
  }

  /**
   * Load messages for current chat
   */
  async loadMessages() {
    if (!this.currentChatId) {
      this.messages = [];
      return;
    }

    this.loading = true;
    this.error = null;

    try {
      const data = await this.api.getMessages(this.currentChatId, this.maxMessages);
      this.messages = data.messages || [];
      this.hasMore = data.has_more || false;
    } catch (err) {
      this.error = err.message;
      console.error('Failed to load messages:', err);
    } finally {
      this.loading = false;
    }
  }

  /**
   * Handle chat selection
   */
  async _handleChatSelected(e) {
    const { chatId } = e.detail;
    this.currentChatId = chatId;
    this._showSidebar = false; // Hide sidebar on mobile
    await this.loadMessages();
  }

  /**
   * Handle new chat
   */
  _handleNewChat() {
    this.currentChatId = null;
    this.messages = [];
    this._showSidebar = false; // Hide sidebar on mobile
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
        this.currentChatId,
        this.maxMessages,
        oldestMessage.id
      );

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
      const response = await this.api.sendMessage(text, this.currentChatId, file);

      // Update or set current chat ID
      if (response.chat_id) {
        const isNewChat = !this.currentChatId;
        this.currentChatId = response.chat_id;

        // If it's a new chat, reload chat list
        if (isNewChat) {
          await this.loadChats();
        }
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
      if (!document.hidden) {
        this._refreshMessages();
        this._refreshChats();
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
    if (this.loading || this.sending || !this.currentChatId) return;

    try {
      const lastMessage = this.messages[this.messages.length - 1];
      const afterId = lastMessage ? lastMessage.id : null;

      const data = await this.api.getMessages(
        this.currentChatId,
        this.maxMessages,
        null,
        afterId
      );

      if (data.messages && data.messages.length > 0) {
        this.messages = [...this.messages, ...data.messages];
      }
    } catch (err) {
      console.error('Refresh failed:', err);
    }
  }

  /**
   * Refresh chat list
   */
  async _refreshChats() {
    if (this.loadingChats) return;

    try {
      const data = await this.api.getChats();
      this.chats = data.chats || [];
    } catch (err) {
      console.error('Chat list refresh failed:', err);
    }
  }

  /**
   * Show sidebar (mobile)
   */
  _showSidebarMobile() {
    this._showSidebar = true;
    this.requestUpdate();
  }

  render() {
    return html`
      <div class="unicom-chat-container ${this.theme}">
        ${this.error ? html`
          <div class="error-banner">${this.error}</div>
        ` : ''}

        <div class="chat-with-sidebar-container">
          <div class="sidebar ${this._showSidebar ? '' : 'hidden'}">
            <chat-list
              .chats=${this.chats}
              .selectedChatId=${this.currentChatId}
              .loading=${this.loadingChats}
              @chat-selected=${this._handleChatSelected}
              @new-chat=${this._handleNewChat}>
            </chat-list>
          </div>

          <div class="chat-main">
            ${!this._showSidebar ? html`
              <button class="mobile-back-btn" @click=${this._showSidebarMobile}>
                ← Back to Chats
              </button>
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
        </div>
      </div>
    `;
  }
}

customElements.define('unicom-chat-with-sidebar', UnicomChatWithSidebar);
