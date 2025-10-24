/**
 * Real-Time WebChat Client
 * Automatically uses WebSocket when available, falls back to polling
 */

import { WebChatAPI } from './api-client.js';

export class RealTimeWebChatClient {
  constructor(baseURL = '/unicom/webchat', wsURL = null) {
    this.baseURL = baseURL;
    this.wsURL = wsURL || this._getWebSocketURL();
    this.api = new WebChatAPI(baseURL);

    // Connection state
    this.ws = null;
    this.connected = false;
    this.useWebSocket = true;  // Try WebSocket first
    this.pollingInterval = null;
    this.pollingRate = 5000;  // 5 seconds default

    // Filters and subscriptions
    this.filters = {};
    this.currentChatId = null;

    // Event handlers
    this.onMessage = null;
    this.onChatUpdate = null;
    this.onChatsUpdate = null;
    this.onConnectionChange = null;
    this.onError = null;

    // Message cache for polling
    this.lastMessageId = null;
  }

  /**
   * Get WebSocket URL from current location
   */
  _getWebSocketURL() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/ws/unicom/webchat/`;
  }

  /**
   * Connect to real-time updates (WebSocket or polling)
   */
  async connect() {
    if (this.useWebSocket) {
      try {
        await this._connectWebSocket();
      } catch (err) {
        console.warn('WebSocket connection failed, falling back to polling:', err);
        this.useWebSocket = false;
        this._startPolling();
      }
    } else {
      this._startPolling();
    }
  }

  /**
   * Disconnect from real-time updates
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
    this.connected = false;
    this._notifyConnectionChange(false);
  }

  /**
   * Set filters for chat list (e.g., project_id, department)
   */
  setFilters(filters) {
    this.filters = filters;
    if (this.ws && this.connected) {
      this._sendWebSocket({
        action: 'subscribe',
        filters: this.filters
      });
    }
  }

  /**
   * Subscribe to a specific chat for real-time updates
   */
  subscribeToChat(chatId) {
    this.currentChatId = chatId;
    if (this.ws && this.connected) {
      this._sendWebSocket({
        action: 'subscribe_chat',
        chat_id: chatId
      });
    }
  }

  /**
   * Unsubscribe from a chat
   */
  unsubscribeFromChat(chatId) {
    if (this.currentChatId === chatId) {
      this.currentChatId = null;
    }
    if (this.ws && this.connected) {
      this._sendWebSocket({
        action: 'unsubscribe_chat',
        chat_id: chatId
      });
    }
  }

  /**
   * Send a message
   */
  async sendMessage(text, chatId = null, mediaFile = null, metadata = null) {
    if (this.ws && this.connected) {
      // Use WebSocket
      return new Promise((resolve, reject) => {
        const messageHandler = (data) => {
          if (data.type === 'message_sent') {
            this.ws.removeEventListener('message', messageHandler);
            if (data.success) {
              resolve(data);
            } else {
              reject(new Error(data.error || 'Failed to send message'));
            }
          }
        };
        this.ws.addEventListener('message', messageHandler);

        this._sendWebSocket({
          action: 'send_message',
          chat_id: chatId,
          text: text,
          metadata: metadata
        });
      });
    } else {
      // Use REST API
      return await this.api.sendMessage(text, chatId, mediaFile, metadata);
    }
  }

  /**
   * Get list of chats
   */
  async getChats(filters = null) {
    const filtersToUse = filters || this.filters;

    if (this.ws && this.connected) {
      // Use WebSocket
      return new Promise((resolve) => {
        const messageHandler = (event) => {
          const data = JSON.parse(event.data);
          if (data.type === 'chats_list') {
            this.ws.removeEventListener('message', messageHandler);
            resolve(data.chats);
          }
        };
        this.ws.addEventListener('message', messageHandler);

        this._sendWebSocket({
          action: 'get_chats',
          filters: filtersToUse
        });
      });
    } else {
      // Use REST API
      const response = await this.api.getChats(filtersToUse);
      return response.chats;
    }
  }

  /**
   * Get messages for a chat
   */
  async getMessages(chatId, limit = 50) {
    if (this.ws && this.connected) {
      // Use WebSocket
      return new Promise((resolve) => {
        const messageHandler = (event) => {
          const data = JSON.parse(event.data);
          if (data.type === 'messages_list' && data.chat_id === chatId) {
            this.ws.removeEventListener('message', messageHandler);
            resolve(data.messages);
          }
        };
        this.ws.addEventListener('message', messageHandler);

        this._sendWebSocket({
          action: 'get_messages',
          chat_id: chatId,
          limit: limit
        });
      });
    } else {
      // Use REST API
      const response = await this.api.getMessages(chatId, limit);
      return response.messages;
    }
  }

  // Private methods

  /**
   * Connect via WebSocket
   */
  _connectWebSocket() {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.wsURL);

        this.ws.onopen = () => {
          this.connected = true;
          this._notifyConnectionChange(true);

          // Subscribe with filters if set
          if (Object.keys(this.filters).length > 0) {
            this._sendWebSocket({
              action: 'subscribe',
              filters: this.filters
            });
          }

          resolve();
        };

        this.ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          this._handleWebSocketMessage(data);
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          if (!this.connected) {
            reject(error);
          } else {
            this._notifyError(error);
          }
        };

        this.ws.onclose = () => {
          this.connected = false;
          this._notifyConnectionChange(false);

          // Attempt reconnection after 5 seconds
          setTimeout(() => {
            if (this.useWebSocket && !this.connected) {
              this._connectWebSocket().catch(() => {
                // Fall back to polling on repeated failure
                this.useWebSocket = false;
                this._startPolling();
              });
            }
          }, 5000);
        };

        // Connection timeout
        setTimeout(() => {
          if (!this.connected) {
            this.ws.close();
            reject(new Error('WebSocket connection timeout'));
          }
        }, 10000);

      } catch (err) {
        reject(err);
      }
    });
  }

  /**
   * Send data via WebSocket
   */
  _sendWebSocket(data) {
    if (this.ws && this.connected) {
      this.ws.send(JSON.stringify(data));
    }
  }

  /**
   * Handle WebSocket message
   */
  _handleWebSocketMessage(data) {
    switch (data.type) {
      case 'new_message':
        if (this.onMessage) {
          this.onMessage(data.message, data.chat_id);
        }
        break;

      case 'chat_update':
        if (this.onChatUpdate) {
          this.onChatUpdate(data.chat);
        }
        break;

      case 'chats_list':
        if (this.onChatsUpdate) {
          this.onChatsUpdate(data.chats);
        }
        break;

      case 'messages_list':
        // Handled by promise in getMessages
        break;

      case 'message_sent':
        // Handled by promise in sendMessage
        break;

      default:
        console.log('Unknown WebSocket message type:', data.type);
    }
  }

  /**
   * Start polling for updates
   */
  _startPolling() {
    this.connected = true;
    this._notifyConnectionChange(true);

    // Poll for new messages
    this.pollingInterval = setInterval(async () => {
      try {
        if (this.currentChatId) {
          // Poll for new messages in current chat
          const response = await this.api.getMessages(
            this.currentChatId,
            50,
            null,
            this.lastMessageId  // Get messages after last known message
          );

          if (response.messages && response.messages.length > 0) {
            // Update last message ID
            this.lastMessageId = response.messages[response.messages.length - 1].id;

            // Notify about new messages
            response.messages.forEach(msg => {
              if (this.onMessage) {
                this.onMessage(msg, this.currentChatId);
              }
            });
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
        this._notifyError(err);
      }
    }, this.pollingRate);
  }

  /**
   * Notify connection change
   */
  _notifyConnectionChange(connected) {
    if (this.onConnectionChange) {
      this.onConnectionChange(connected, this.useWebSocket ? 'websocket' : 'polling');
    }
  }

  /**
   * Notify error
   */
  _notifyError(error) {
    if (this.onError) {
      this.onError(error);
    }
  }

  /**
   * Set polling rate (in milliseconds)
   */
  setPollingRate(ms) {
    this.pollingRate = ms;
    if (this.pollingInterval && !this.useWebSocket) {
      // Restart polling with new rate
      clearInterval(this.pollingInterval);
      this._startPolling();
    }
  }

  /**
   * Check if using WebSocket
   */
  isUsingWebSocket() {
    return this.connected && this.useWebSocket;
  }

  /**
   * Check if connected
   */
  isConnected() {
    return this.connected;
  }
}
