/**
 * Message Input Component
 * Textarea, send button, and media upload
 */
import { LitElement, html, css } from 'lit';
import { inputStyles } from '../webchat-styles.js';
import './media-preview.js';

export class MessageInput extends LitElement {
  static properties = {
    disabled: { type: Boolean },
    inputText: { type: String, state: true },
    previewFile: { type: Object, state: true },
  };

  static styles = [inputStyles];

  constructor() {
    super();
    this.disabled = false;
    this.inputText = '';
    this.previewFile = null;
  }

  _handleInput(e) {
    this.inputText = e.target.value;
    // Auto-resize textarea
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  }

  _handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this._handleSend();
    }
  }

  _handleSend() {
    if (this.disabled) return;

    const text = this.inputText.trim();
    if (!text && !this.previewFile) return;

    this.dispatchEvent(new CustomEvent('send-message', {
      detail: {
        text: text,
        file: this.previewFile,
      },
      bubbles: true,
      composed: true,
    }));

    // Clear input
    this.inputText = '';
    this.previewFile = null;

    // Reset textarea height
    const textarea = this.shadowRoot.querySelector('textarea');
    if (textarea) {
      textarea.style.height = 'auto';
    }
  }

  _handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file type
    const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'audio/mpeg', 'audio/ogg', 'audio/wav'];
    if (!validTypes.includes(file.type)) {
      alert('Please select a valid image or audio file');
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB');
      return;
    }

    this.previewFile = file;
    // Clear the input so the same file can be selected again
    e.target.value = '';
  }

  _handleRemoveFile() {
    this.previewFile = null;
  }

  render() {
    return html`
      <div class="message-input-container">
        ${this.previewFile ? html`
          <media-preview
            .file=${this.previewFile}
            @remove=${this._handleRemoveFile}>
          </media-preview>
        ` : ''}

        <div class="input-row">
          <input
            type="file"
            id="media-upload"
            accept="image/*,audio/*"
            @change=${this._handleFileSelect}
            style="display: none;">

          <button
            class="attach-btn"
            @click=${() => this.shadowRoot.getElementById('media-upload').click()}
            ?disabled=${this.disabled}
            title="Attach media">
            📎
          </button>

          <textarea
            .value=${this.inputText}
            @input=${this._handleInput}
            @keydown=${this._handleKeyDown}
            placeholder="Type a message..."
            ?disabled=${this.disabled}
            rows="1"></textarea>

          <button
            class="send-btn"
            @click=${this._handleSend}
            ?disabled=${this.disabled || (!this.inputText.trim() && !this.previewFile)}>
            Send
          </button>
        </div>
      </div>
    `;
  }
}

customElements.define('message-input', MessageInput);
