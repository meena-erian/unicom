/**
 * Message List Component
 * Scrollable container for messages with pagination
 */
import { LitElement, html, css } from 'lit';
import { listStyles } from '../webchat-styles.js';
import './message-item.js';

export class MessageList extends LitElement {
  static properties = {
    messages: { type: Array },
    loading: { type: Boolean },
    hasMore: { type: Boolean },
  };

  static styles = [listStyles];

  constructor() {
    super();
    this.messages = [];
    this.loading = false;
    this.hasMore = false;
    this._shouldScrollToBottom = true;
  }

  updated(changedProperties) {
    super.updated(changedProperties);

    if (changedProperties.has('messages')) {
      // Scroll to bottom when new messages arrive
      if (this._shouldScrollToBottom) {
        this._scrollToBottom();
      }
      this._shouldScrollToBottom = true;
    }
  }

  _scrollToBottom() {
    requestAnimationFrame(() => {
      const container = this.shadowRoot.querySelector('.message-list');
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    });
  }

  _handleEditMessage(e) {
    // Pass through edit message events to parent
    this.dispatchEvent(new CustomEvent('edit-message', {
      detail: e.detail,
      bubbles: true,
      composed: true,
    }));
  }

  _handleBranchNavigation(e) {
    console.log('Message list received branch navigation:', e.detail);
    this.dispatchEvent(new CustomEvent('branch-navigation', {
      detail: e.detail,
      bubbles: true,
      composed: true,
    }));
  }

  _handleScroll(e) {
    // Detect if user is at the top for "load more"
    // This is handled by the parent component
  }

  _loadMore() {
    this._shouldScrollToBottom = false;
    this.dispatchEvent(new CustomEvent('load-more', {
      bubbles: true,
      composed: true,
    }));
  }

  render() {
    if (this.messages.length === 0 && !this.loading) {
      return html`
        <div class="message-list">
          <div class="empty-state">
            <div class="empty-state-icon">💬</div>
            <div>No messages yet. Start the conversation!</div>
          </div>
        </div>
      `;
    }

    return html`
      <div class="message-list" @scroll=${this._handleScroll}>
        ${this.loading ? html`
          <div class="loading-spinner">Loading messages...</div>
        ` : ''}

        ${this.hasMore && !this.loading ? html`
          <button @click=${this._loadMore} class="load-more-btn">
            Load earlier messages
          </button>
        ` : ''}

        ${this.messages.map(msg => html`
          <message-item 
            .message=${msg} 
            @edit-message=${this._handleEditMessage}
            @branch-navigation=${this._handleBranchNavigation}>
          </message-item>
        `)}
      </div>
    `;
  }
}

customElements.define('message-list', MessageList);
