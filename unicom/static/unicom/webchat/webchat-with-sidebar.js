/**
 * WebChat Component with Sidebar
 * Multi-chat support with chat list sidebar
 * Supports both WebSocket (if available) and polling fallback
 */
import { LitElement, html, css } from 'lit';
import { baseStyles } from './webchat-styles.js';
import { RealTimeWebChatClient } from './utils/realtime-client.js';
import './components/chat-list.js';
import './components/message-list.js';
import './components/message-input.js';

const WEBCHAT_UI_VERSION = '2025.02.15-rc4';
console.info(`[Unicom WebChat] bundle loaded (v${WEBCHAT_UI_VERSION})`);

export class UnicomChatWithSidebar extends LitElement {
  static properties = {
    apiBase: { type: String, attribute: 'api-base' },
    wsUrl: { type: String, attribute: 'ws-url' },
    channelId: { type: Number, attribute: 'channel-id' },
    maxMessages: { type: Number, attribute: 'max-messages' },
    theme: { type: String },
    autoRefresh: { type: Number, attribute: 'auto-refresh' },
    filters: { type: Object },  // Custom filters (e.g., {metadata__project_id: 123})
    metadataDefaults: { type: Object, attribute: 'metadata-defaults' }, // Default metadata to send with every message
    disableWebsocket: { type: Boolean, attribute: 'disable-websocket' },

    // Internal state
    chats: { type: Array, state: true },
    currentChatId: { type: String, state: true },
    messages: { type: Array, state: true },
    loading: { type: Boolean, state: true },
    loadingChats: { type: Boolean, state: true },
    sending: { type: Boolean, state: true },
    error: { type: String, state: true },
    hasMore: { type: Boolean, state: true },
    connectionStatus: { type: String, state: true },  // 'connected', 'disconnected'
    connectionType: { type: String, state: true },     // 'websocket', 'polling'
  };

  static styles = [
    baseStyles,
    css`
      .chat-with-sidebar-container {
        display: flex;
        flex: 1 1 auto;
        min-height: 0;
        max-width: 100%;
        width: 100%;
        overflow: hidden;
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
        width: 100%;
        min-height: 0;
      }

      @container (max-width: 768px) {
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
          background: var(--sidebar-header-bg, var(--primary-color));
          color: var(--sidebar-header-text, #ffffff);
          border: none;
          border-bottom: 1px solid var(--sidebar-border-color, var(--border-color));
          cursor: pointer;
          width: 100%;
          text-align: left;
          font-size: 1em;
          transition: background 0.2s ease;
        }

        .mobile-back-btn:hover {
          background: var(--sidebar-header-bg, var(--primary-color));
          filter: brightness(0.95);
        }
      }

      @container (min-width: 769px) {
        .mobile-back-btn {
          display: none;
        }
      }
    `
  ];

  constructor() {
    super();
    this.apiBase = '/unicom/webchat';
    this.wsUrl = null;
    this.channelId = null;
    this.maxMessages = 50;
    this.theme = 'light';
    this.autoRefresh = 5;
    this.filters = {};
    this.metadataDefaults = {};
    this.disableWebsocket = false;

    this.chats = [];
    this.currentChatId = null;
    this.messages = [];
    this.loading = false;
    this.loadingChats = false;
    this.sending = false;
    this.error = null;
    this.hasMore = false;
    this.connectionStatus = 'disconnected';
    this.connectionType = 'polling';

    this.client = null;
    this._showSidebar = true;
    this._deletingChatId = null;
  }

  connectedCallback() {
    super.connectedCallback();

    // Initialize real-time client
    this.client = new RealTimeWebChatClient(this.apiBase, this.wsUrl, {
      disableWebsocket: this.disableWebsocket,
    });

    // Set up event handlers
    this.client.onMessage = (message, chatId) => this._handleNewMessage(message, chatId);
    this.client.onChatsUpdate = (chats) => this._handleChatsUpdate(chats);
    this.client.onConnectionChange = (connected, type) => {
      this.connectionStatus = connected ? 'connected' : 'disconnected';
      this.connectionType = type;
    };
    this.client.onError = (error) => {
      console.error('WebChat error:', error);
    };

    // Set polling rate from autoRefresh
    if (this.autoRefresh > 0) {
      this.client.setPollingRate(this.autoRefresh * 1000);
    }

    // Set filters
    if (Object.keys(this.filters).length > 0) {
      this.client.setFilters(this.filters);
    }

    // Connect and load initial data
    this._initializeConnection();
  }

  updated(changedProperties) {
    super.updated(changedProperties);

    if (changedProperties.has('disableWebsocket') && this.client) {
      this.client.setWebSocketEnabled(!this.disableWebsocket);
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.client) {
      this.client.disconnect();
    }
  }

  /**
   * Initialize connection and load data
   */
  async _initializeConnection() {
    try {
      await this.client.connect();
      await this.loadChats();
    } catch (err) {
      this.error = 'Failed to connect: ' + err.message;
      console.error('Connection failed:', err);
    }
  }

  /**
   * Load list of chats
   */
  async loadChats() {
    this.loadingChats = true;

    try {
      const chats = await this.client.getChats(this.filters);
      this.chats = chats || [];

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
      // Subscribe to chat for real-time updates
      this.client.subscribeToChat(this.currentChatId);

      const messages = await this.client.getMessages(this.currentChatId, this.maxMessages);
      this.messages = messages || [];
      this.client.updateBaselineFromMessages(this.messages);
      // Note: hasMore not supported in current getMessages - could be added later
      this.hasMore = false;
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

    // Unsubscribe from old chat
    if (this.currentChatId) {
      this.client.unsubscribeFromChat(this.currentChatId);
    }

    this.currentChatId = chatId;
    this._showSidebar = false; // Hide sidebar on mobile
    await this.loadMessages();
  }

  /**
   * Handle new chat
   */
  _handleNewChat() {
    // Unsubscribe from current chat
    if (this.currentChatId) {
      this.client.unsubscribeFromChat(this.currentChatId);
    }

    this.currentChatId = null;
    this.messages = [];
    this._showSidebar = false; // Hide sidebar on mobile
  }

  /**
   * Load more (older) messages
   */
  async _handleLoadMore() {
    // Pagination not implemented in real-time client yet
    // Could be added later
    console.log('Load more not implemented yet');
  }

  /**
   * Send a message
   */
  async _handleSendMessage(e) {
    const { text, file, replyToMessageId } = e.detail;

    if (this.sending) return;
    if (!text && !file) return;

    this.sending = true;
    this.error = null;

    try {
      // Build options object
      const options = {};
      
      // Include filter metadata when creating a new chat
      if (!this.currentChatId) {
        options.metadata = { ...(this.filters || {}), ...(this.metadataDefaults || {}) };
      } else if (this.metadataDefaults) {
        options.metadata = this.metadataDefaults;
      }
      
      // Include reply_to_message_id for message editing/branching
      if (replyToMessageId) {
        options.reply_to_message_id = replyToMessageId;
      }

      const response = await this.client.sendMessage(text, this.currentChatId, file, options);

      // Update or set current chat ID
      if (response.chat_id) {
        const isNewChat = !this.currentChatId;
        this.currentChatId = response.chat_id;

        // If it's a new chat, reload chat list and subscribe to it
        if (isNewChat) {
          await this.loadChats();
          this.client.subscribeToChat(this.currentChatId);
        }
      }

      // Add the sent message to the list (if not already added by real-time update)
      if (response.message) {
        const messageExists = this.messages.some(m => m.id === response.message.id);
        if (!messageExists) {
          this.messages = [...this.messages, response.message];
        }
      }
    } catch (err) {
      this.error = err.message;
      console.error('Failed to send message:', err);
    } finally {
      this.sending = false;
    }
  }

  /**
   * Handle new message from real-time updates
   */
  _handleNewMessage(message, chatId) {
    // Only add message if it's for the current chat
    if (chatId === this.currentChatId) {
      // Check if message already exists (avoid duplicates)
      const messageExists = this.messages.some(m => m.id === message.id);
      if (!messageExists) {
        this.messages = [...this.messages, message];
      }
    }

    // Update chat list to reflect new message
    this.loadChats();
  }

  /**
   * Handle chats update from real-time updates
   */
  _handleChatsUpdate(chats) {
    this.chats = chats || [];
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
              @new-chat=${this._handleNewChat}
              @delete-chat=${this._handleDeleteChat}>
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
              @load-more=${this._handleLoadMore}
              @edit-message=${this._handleEditMessage}>
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

  /**
   * Handle edit message requests.
   */
  _handleEditMessage(e) {
    const { messageId } = e.detail;
    
    // Find the message to edit
    const message = this.messages.find(m => m.id === messageId);
    if (!message) return;
    
    // Set edit mode in message input
    const messageInput = this.shadowRoot.querySelector('message-input');
    if (messageInput) {
      messageInput.editingMessageId = messageId;
      messageInput.inputText = message.text || '';
      
      // Focus the textarea
      setTimeout(() => {
        const textarea = messageInput.shadowRoot?.querySelector('textarea');
        if (textarea) {
          textarea.focus();
          textarea.setSelectionRange(textarea.value.length, textarea.value.length);
        }
      }, 100);
    }
  }

  /**
   * Handle chat deletion requests.
   */
  async _handleDeleteChat(e) {
    const { chatId } = e.detail || {};
    if (!chatId || this._deletingChatId === chatId) {
      return;
    }

    this._deletingChatId = chatId;
    this.error = null;

    try {
      await this.client.api.deleteChat(chatId, true);

      if (this.currentChatId === chatId) {
        this.client.unsubscribeFromChat(chatId);
        this.currentChatId = null;
        this.messages = [];
        this._showSidebar = true;
      }

      await this.loadChats();
    } catch (err) {
      this.error = err.message || 'Failed to delete chat';
      console.error('Failed to delete chat:', err);
    } finally {
      this._deletingChatId = null;
    }
  }
}

customElements.define('unicom-chat-with-sidebar', UnicomChatWithSidebar);
