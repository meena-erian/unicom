/**
 * WebChat API Client
 * Handles all HTTP requests to the WebChat backend APIs
 */

export class WebChatAPI {
  constructor(baseURL = '/unicom/webchat') {
    this.baseURL = baseURL;
  }

  /**
   * Extract CSRF token from cookies
   */
  async getCSRFToken() {
    const name = 'csrftoken';
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [key, value] = cookie.trim().split('=');
      if (key === name) return value;
    }
    return null;
  }

  /**
   * Send a message (text or media)
   * @param {string} text - Message text
   * @param {string|null} chatId - Optional chat ID
   * @param {File|null} mediaFile - Optional media file (image/audio)
   * @param {Object|null} metadata - Optional metadata for new chat creation (e.g., {project_id: 123})
   * @returns {Promise<Object>} Response data
   */
  async sendMessage(text, chatId = null, mediaFile = null, metadata = null) {
    const formData = new FormData();
    formData.append('text', text);
    if (chatId) formData.append('chat_id', chatId);
    if (mediaFile) formData.append('media', mediaFile);
    if (metadata) formData.append('metadata', JSON.stringify(metadata));

    const response = await fetch(`${this.baseURL}/send/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': await this.getCSRFToken(),
      },
      body: formData,
      credentials: 'same-origin',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Failed to send message');
    }
    return await response.json();
  }

  /**
   * Get messages for a chat
   * @param {string|null} chatId - Optional chat ID
   * @param {number} limit - Max messages to fetch
   * @param {string|null} before - Cursor for pagination (message ID)
   * @param {string|null} after - Cursor for new messages (message ID)
   * @returns {Promise<Object>} Response with messages array
   */
  async getMessages(chatId = null, limit = 50, before = null, after = null) {
    const params = new URLSearchParams();
    if (chatId) params.append('chat_id', chatId);
    params.append('limit', limit);
    if (before) params.append('before', before);
    if (after) params.append('after', after);

    const response = await fetch(`${this.baseURL}/messages/?${params}`, {
      credentials: 'same-origin',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Failed to fetch messages');
    }
    return await response.json();
  }

  /**
   * Get list of chats with optional filtering
   * @param {Object} filters - Filter parameters
   *   Examples:
   *   - {is_archived: false} - Only non-archived chats
   *   - {metadata__project_id: 123} - Chats for project 123
   *   - {metadata__department: 'sales'} - Chats for sales department
   * @returns {Promise<Object>} Response with chats array
   */
  async getChats(filters = {}) {
    const params = new URLSearchParams();

    // Add all filter parameters
    for (const [key, value] of Object.entries(filters)) {
      params.append(key, value);
    }

    const response = await fetch(`${this.baseURL}/chats/?${params}`, {
      credentials: 'same-origin',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Failed to fetch chats');
    }
    return await response.json();
  }

  /**
   * Update chat (rename or archive)
   * @param {string} chatId - Chat ID
   * @param {Object} updates - Fields to update (title, is_archived)
   * @returns {Promise<Object>} Response data
   */
  async updateChat(chatId, updates) {
    const response = await fetch(`${this.baseURL}/chat/${chatId}/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': await this.getCSRFToken(),
      },
      body: JSON.stringify(updates),
      credentials: 'same-origin',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Failed to update chat');
    }
    return await response.json();
  }

  /**
   * Delete/archive chat
   * @param {string} chatId - Chat ID
   * @param {boolean} hardDelete - If true, permanently delete. Otherwise archive.
   * @returns {Promise<Object>} Response data
   */
  async deleteChat(chatId, hardDelete = false) {
    const params = hardDelete ? '?hard_delete=true' : '';
    const response = await fetch(`${this.baseURL}/chat/${chatId}/delete/${params}`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': await this.getCSRFToken(),
      },
      credentials: 'same-origin',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Failed to delete chat');
    }
    return await response.json();
  }
}
