/**
 * Message Item Component
 * Renders individual message with media support
 */
import { LitElement, html, css } from 'lit';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { messageStyles } from '../webchat-styles.js';
import { formatTimestamp } from '../utils/datetime-formatter.js';

export class MessageItem extends LitElement {
  static properties = {
    message: { type: Object },
    loadingButtons: { type: Set },
  };

  static styles = [messageStyles];

  constructor() {
    super();
    this.message = null;
    this.loadingButtons = new Set();
  }

  _sanitizeHTML(html) {
    // Basic HTML sanitization
    // For production, consider using a library like DOMPurify
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML;
  }

  _formatTimestamp(timestamp) {
    return formatTimestamp(timestamp);
  }

  _renderInteractiveButtons(buttons) {
    if (!buttons || !buttons.length) return '';
    
    return html`
      <div class="interactive-buttons">
        ${buttons.map(row => html`
          <div class="button-row">
            ${row.map(button => {
              const isLoading = this.loadingButtons.has(button.callback_execution_id);
              return html`
                <button 
                  class="interactive-btn ${button.style || 'primary'}"
                  @click=${() => this._handleButtonClick(button)}
                  ?disabled=${button.disabled || isLoading}>
                  ${isLoading ? '⏳' : button.text}
                </button>
              `;
            })}
          </div>
        `)}
      </div>
    `;
  }

  _handleButtonClick(button) {
    if (button.type === 'url') {
      window.open(button.url, '_blank');
      return;
    }
    
    if (button.type === 'callback' && button.callback_execution_id) {
      // Prevent multiple clicks
      if (this.loadingButtons.has(button.callback_execution_id)) return;
      
      // Add to loading set
      this.loadingButtons.add(button.callback_execution_id);
      this.requestUpdate();
      
      // Send button click to backend
      fetch('/unicom/webchat/button-click/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this._getCSRFToken()
        },
        body: JSON.stringify({
          callback_execution_id: button.callback_execution_id
        })
      }).then(response => {
        if (response.ok) {
          // Refresh messages to show any updates
          this.dispatchEvent(new CustomEvent('refresh-messages', {
            bubbles: true,
            composed: true
          }));
        } else {
          console.error('Button click failed:', response.statusText);
        }
      }).catch(error => {
        console.error('Button click error:', error);
      }).finally(() => {
        // Remove from loading set
        this.loadingButtons.delete(button.callback_execution_id);
        this.requestUpdate();
      });
    }
  }

  _getCSRFToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'csrftoken') {
        return value;
      }
    }
    return '';
  }

  _openImageModal(url) {
    // Open image in new tab for now
    // Could be enhanced with a lightbox modal in future
    window.open(url, '_blank');
  }

  _renderMessageContent(message) {
    switch (message.media_type) {
      case 'text':
        return html`<div class="message-text">${message.text}</div>`;

      case 'html':
        // Render HTML content (sanitized)
        return html`<div class="message-html">${unsafeHTML(message.html || message.text)}</div>`;

      case 'image':
        return html`
          <div class="message-media">
            ${message.text && message.text !== '**Image**' ?
              html`<div class="message-caption">${message.text}</div>` : ''}
            ${message.media_url ?
              html`<img src="${message.media_url}" alt="Image" @click=${() => this._openImageModal(message.media_url)}>` :
              html`<div style="color: red;">Image file is missing.</div>`
            }
          </div>
        `;

      case 'audio':
        return html`
          <div class="message-media">
            ${message.text && message.text !== '**Voice Message**' && message.text !== '**Audio**' ?
              html`<div class="message-caption">${message.text}</div>` : ''}
            ${message.media_url ?
              html`<audio controls src="${message.media_url}"></audio>` :
              html`<div style="color: red;">Audio file is missing.</div>`
            }
          </div>
        `;

      case 'tool_call':
        // Render as status line with loading or completion state
        console.log('Tool call message:', message); // Debug log
        const toolName = message.raw?.tool_call?.name || message.text?.match(/Tool call: (.+)/)?.[1] || 'tool';
        const status = message._toolStatus || 'pending';
        
        if (status === 'pending') {
          return html`
            <div class="tool-status pending">
              <span class="tool-icon">⚙️</span>
              using ${toolName}<span class="loading-dots">...</span>
            </div>
          `;
        } else {
          return html`
            <div class="tool-status completed">
              <span class="tool-icon">✅</span>
              ${toolName} completed
            </div>
          `;
        }

      case 'tool_response':
        // This should not render separately anymore (handled by tool_call)
        return html``;

      default:
        return html`<div class="message-text">${message.text}</div>`;
    }
  }

  _handleEditMessage() {
    this.dispatchEvent(new CustomEvent('edit-message', {
      detail: { messageId: this.message.id },
      bubbles: true,
      composed: true,
    }));
  }

  _handleBranchNavigation(direction) {
    console.log('Branch navigation clicked:', direction, 'for message:', this.message.id);
    
    // Stop event from bubbling to prevent double handling
    const event = new CustomEvent('branch-navigation', {
      detail: { 
        groupId: this.message.branchInfo.groupId,
        direction: direction
      },
      bubbles: true,
      composed: true,
    });
    
    this.dispatchEvent(event);
    console.log('Branch navigation event dispatched');
  }

  render() {
    if (!this.message) return html``;

    const message = this.message;
    const isUserMessage = message.is_outgoing === false;
    const mediaType = message.media_type;
    
    // Handle tool calls as simple status lines (no bubble)
    if (mediaType === 'tool_call') {
      return html`
        <div class="message-item system">
          ${this._renderMessageContent(message)}
        </div>
      `;
    }

    const alignment = isUserMessage ? 'outgoing' : 'incoming';
    const classes = ['message-item', alignment];
    const bubbleClasses = ['message-bubble'];

    if (message.is_outgoing === null) {
      classes.push('system');
    }

    if (['image', 'audio'].includes(mediaType)) {
      bubbleClasses.push('media');
    }
    if (mediaType === 'audio') {
      bubbleClasses.push('audio');
    }

    return html`
      <div class="${classes.join(' ')}">
        ${!isUserMessage && message.sender_name ? html`
          <div class="sender-name">${message.sender_name}</div>
        ` : ''}
        <div class="${bubbleClasses.join(' ')}">
          ${this._renderMessageContent(message)}
          <div class="message-footer">
            <div class="message-timestamp">${this._formatTimestamp(message.timestamp)}</div>
            <div class="message-actions">
              ${message.branchInfo ? html`
                <div class="branch-navigation">
                  <button 
                    class="branch-nav-btn" 
                    ?disabled=${!message.branchInfo.canGoPrev}
                    @click=${() => this._handleBranchNavigation('prev')}>
                    ‹
                  </button>
                  <span class="branch-counter">
                    ${message.branchInfo.current} / ${message.branchInfo.total}
                  </span>
                  <button 
                    class="branch-nav-btn" 
                    ?disabled=${!message.branchInfo.canGoNext}
                    @click=${() => this._handleBranchNavigation('next')}>
                    ›
                  </button>
                </div>
              ` : ''}
              ${isUserMessage ? html`
                <button class="edit-btn" @click=${this._handleEditMessage} title="Edit message">✏️</button>
              ` : ''}
            </div>
          </div>
        </div>
        ${this._renderInteractiveButtons(message.interactive_buttons)}
      </div>
    `;
  }
}

customElements.define('message-item', MessageItem);
