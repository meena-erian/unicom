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
    processedMessages: { type: Array, state: true },  // Messages with branch info
    branchSelections: { type: Object, state: true },  // Track selected branch per group
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
    this.processedMessages = [];
    this.branchSelections = {};
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
    this._branchNavigationTimeout = null; // Add debounce timeout
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
  /**
   * Process messages to handle branching with inline navigation
   */
  _processMessagesWithBranching(messages) {
    if (!messages || messages.length === 0) return [];

    // Create message lookup and branch groups
    const msgById = new Map();
    const branchGroups = new Map();
    
    messages.forEach(msg => {
      msgById.set(msg.id, msg);
      
      // Group by reply_to_message_id
      const replyTo = msg.reply_to_message_id;
      if (replyTo) {
        if (!branchGroups.has(replyTo)) {
          branchGroups.set(replyTo, []);
        }
        branchGroups.get(replyTo).push(msg);
      }
    });

    // Sort branch groups by timestamp
    branchGroups.forEach(group => {
      group.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    });

    // Clean up stale branch selections
    const validGroupIds = new Set(branchGroups.keys());
    const cleanedSelections = {};
    Object.keys(this.branchSelections).forEach(groupId => {
      if (validGroupIds.has(groupId)) {
        const group = branchGroups.get(groupId);
        const currentSelection = this.branchSelections[groupId];
        if (currentSelection < group.length) {
          cleanedSelections[groupId] = currentSelection;
        } else {
          cleanedSelections[groupId] = group.length - 1;
        }
      }
    });
    this.branchSelections = cleanedSelections;

    // Build selected path
    const pathIds = new Set();
    const visibleMessageIds = new Set();
    const visibleReplyToIds = new Set();
    
    // Start from root messages
    const rootMessages = messages.filter(m => !m.reply_to_message_id);
    
    // Build path forward, tracking visible messages
    rootMessages.forEach(root => {
      this._buildPathForwardWithTracking(root, msgById, branchGroups, pathIds, visibleMessageIds, visibleReplyToIds);
    });

    // Build result with branch info
    const result = [];
    messages.forEach(msg => {
      if (pathIds.has(msg.id)) {
        const replyTo = msg.reply_to_message_id;
        let branchInfo = null;
        
        if (replyTo && branchGroups.has(replyTo)) {
          const group = branchGroups.get(replyTo);
          if (group.length > 1) {
            const currentIndex = group.findIndex(m => m.id === msg.id);
            branchInfo = {
              current: currentIndex + 1,
              total: group.length,
              groupId: replyTo,
              canGoPrev: currentIndex > 0,
              canGoNext: currentIndex < group.length - 1
            };
          }
        }
        
        result.push({ ...msg, branchInfo });
      }
    });

    return result.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  }

  /**
   * Build path forward with tracking of visible message IDs
   */
  _buildPathForwardWithTracking(message, msgById, branchGroups, pathIds, visibleMessageIds, visibleReplyToIds) {
    pathIds.add(message.id);
    visibleMessageIds.add(message.id);
    if (message.reply_to_message_id) {
      visibleReplyToIds.add(message.reply_to_message_id);
    }
    
    // Find children of this message
    const children = branchGroups.get(message.id) || [];
    
    if (children.length === 0) {
      return;
    }
    
    // Select which child to follow
    let selectedChild;
    if (children.length === 1) {
      selectedChild = children[0];
    } else {
      const selectedIndex = this.branchSelections[message.id] !== undefined 
        ? this.branchSelections[message.id] 
        : children.length - 1;
      selectedChild = children[selectedIndex];
    }
    
    // Continue building path from selected child
    this._buildPathForwardWithTracking(selectedChild, msgById, branchGroups, pathIds, visibleMessageIds, visibleReplyToIds);
  }

  /**
   * Build path forward from a given message using branch selections
   */
  _buildPathForward(message, msgById, branchGroups, pathIds) {
    pathIds.add(message.id);
    
    // Find children of this message
    const children = branchGroups.get(message.id) || [];
    
    if (children.length === 0) {
      return;
    }
    
    // Select which child to follow
    let selectedChild;
    if (children.length === 1) {
      selectedChild = children[0];
    } else {
      const selectedIndex = this.branchSelections[message.id] !== undefined 
        ? this.branchSelections[message.id] 
        : children.length - 1;
      selectedChild = children[selectedIndex];
    }
    
    // Continue building path from selected child
    this._buildPathForward(selectedChild, msgById, branchGroups, pathIds);
  }

  /**
   * Handle branch navigation (prev/next)
   */
  _handleBranchNavigation(e) {
    e.stopPropagation();
    
    // Debounce to prevent multiple rapid executions
    if (this._branchNavigationTimeout) {
      clearTimeout(this._branchNavigationTimeout);
    }
    
    this._branchNavigationTimeout = setTimeout(() => {
      this._processBranchNavigation(e.detail);
      this._branchNavigationTimeout = null;
    }, 10);
  }

  /**
   * Process branch navigation after debounce
   */
  _processBranchNavigation(detail) {
    console.log('Main component received branch navigation:', detail);
    const { groupId, direction } = detail;
    
    // Find the group
    const group = this.messages.filter(m => m.reply_to_message_id === groupId)
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    
    console.log('Found group with', group.length, 'messages for groupId:', groupId);
    
    if (group.length <= 1) return;
    
    // Get current selection
    const currentSelection = this.branchSelections[groupId] !== undefined 
      ? this.branchSelections[groupId] 
      : group.length - 1;
    
    console.log('Current selection:', currentSelection);
    
    let newSelection = currentSelection;
    if (direction === 'prev' && currentSelection > 0) {
      newSelection = currentSelection - 1;
    } else if (direction === 'next' && currentSelection < group.length - 1) {
      newSelection = currentSelection + 1;
    }
    
    console.log('New selection:', newSelection);
    
    if (newSelection !== currentSelection) {
      this.branchSelections = {
        ...this.branchSelections,
        [groupId]: newSelection
      };
      
      console.log('Updated branchSelections:', this.branchSelections);
      this.processedMessages = this._processMessagesWithBranching(this.messages);
      console.log('Reprocessed messages, new count:', this.processedMessages.length);
      this.requestUpdate();
    }
  }

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
      this.processedMessages = this._processMessagesWithBranching(this.messages);
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
    this.processedMessages = [];
    this.branchSelections = {};
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
      
      // Determine reply_to_message_id
      if (replyToMessageId) {
        options.reply_to_message_id = replyToMessageId;
      } else if (this.processedMessages.length > 0) {
        // New message - reply to last visible assistant message
        const lastAssistantMessage = [...this.processedMessages]
          .reverse()
          .find(msg => msg.is_outgoing === true);
        
        if (lastAssistantMessage) {
          options.reply_to_message_id = lastAssistantMessage.id;
        }
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
      // Skip immediate addition for edits - let real-time update handle branching logic
      if (response.message && !options.reply_to_message_id) {
        const messageExists = this.messages.some(m => m.id === response.message.id);
        if (!messageExists) {
          this.messages = [...this.messages, response.message];
          this.processedMessages = this._processMessagesWithBranching(this.messages);
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
    console.log('New message received:', message.id, 'for chat:', chatId);
    console.log('Message reply_to_message_id:', message.reply_to_message_id);
    
    // Only add message if it's for the current chat
    if (chatId === this.currentChatId) {
      // Check if message already exists
      const existingIndex = this.messages.findIndex(m => m.id === message.id);
      if (existingIndex >= 0) {
        // Update existing message to ensure all fields are current
        console.log('Updating existing message with latest data');
        this.messages[existingIndex] = message;
        this.messages = [...this.messages]; // Trigger reactivity
        this.processedMessages = this._processMessagesWithBranching(this.messages);
        this.requestUpdate();
      } else {
        console.log('Adding new message to chat');
        
        // Add the new message
        this.messages = [...this.messages, message];
        
        // If this message creates a branch, ensure it's selected as the latest
        if (message.reply_to_message_id) {
          const siblings = this.messages.filter(m => m.reply_to_message_id === message.reply_to_message_id);
          if (siblings.length > 1) {
            // Sort siblings by timestamp and select the latest (this message)
            siblings.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            const messageIndex = siblings.findIndex(m => m.id === message.id);
            this.branchSelections = {
              ...this.branchSelections,
              [message.reply_to_message_id]: messageIndex
            };
          }
        }
        
        this.processedMessages = this._processMessagesWithBranching(this.messages);
        console.log('Processed messages:', this.processedMessages.length);
        
        this.requestUpdate();
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
              .messages=${this.processedMessages}
              .loading=${this.loading}
              .hasMore=${this.hasMore}
              @load-more=${this._handleLoadMore}
              @edit-message=${this._handleEditMessage}
              @branch-navigation=${this._handleBranchNavigation}>
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
    
    console.log('Looking for message to edit:', messageId);
    console.log('Available in this.messages:');
    this.messages.forEach(m => console.log(`  ${m.id}: reply_to=${m.reply_to_message_id}`));
    console.log('Available in this.processedMessages:');
    this.processedMessages.forEach(m => console.log(`  ${m.id}: reply_to=${m.reply_to_message_id}`));
    
    // Find the message to edit in both raw messages and processed messages
    let message = this.messages.find(m => m.id === messageId);
    if (!message) {
      message = this.processedMessages.find(m => m.id === messageId);
    }
    
    if (!message) {
      console.error('Message not found for editing:', messageId);
      return;
    }
    
    console.log('Found message for editing:', message);
    console.log('Editing message:', messageId, 'reply_to:', message.reply_to_message_id);
    
    // Set edit mode in message input
    const messageInput = this.shadowRoot.querySelector('message-input');
    if (messageInput) {
      // For editing: set reply_to_message_id to the message's parent (creates branch)
      // If message has no parent (root message), use null to create branch at root level
      messageInput.editingMessageId = message.reply_to_message_id || null;
      messageInput.inputText = message.text || '';
      
      console.log('Set editingMessageId to:', message.reply_to_message_id || null);
      
      // Force update of message input to trigger edit mode
      messageInput.requestUpdate();
      
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
