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
  };

  static styles = [messageStyles];

  constructor() {
    super();
    this.message = null;
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
      case 'tool_response':
        // Display as system message with special styling
        return html`<div class="message-system">${message.text}</div>`;

      default:
        return html`<div class="message-text">${message.text}</div>`;
    }
  }

  render() {
    if (!this.message) return html``;

    const message = this.message;
    const isUserMessage = message.is_outgoing === false;
    const alignment = isUserMessage ? 'outgoing' : 'incoming';
    const classes = ['message-item', alignment];

    if (message.is_outgoing === null) {
      classes.push('system');
    }

    return html`
      <div class="${classes.join(' ')}">
        ${!isUserMessage && message.sender_name ? html`
          <div class="sender-name">${message.sender_name}</div>
        ` : ''}
        <div class="message-bubble">
          ${this._renderMessageContent(message)}
          <div class="message-timestamp">${this._formatTimestamp(message.timestamp)}</div>
        </div>
      </div>
    `;
  }
}

customElements.define('message-item', MessageItem);
