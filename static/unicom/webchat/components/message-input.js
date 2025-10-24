/**
 * Message Input Component
 * Textarea, send button, and media upload
 */
import { LitElement, html } from 'lit';
import { inputStyles } from '../webchat-styles.js';
import './media-preview.js';
import './voice-recorder.js';

export class MessageInput extends LitElement {
  static properties = {
    disabled: { type: Boolean },
    inputText: { type: String, state: true },
    previewFile: { type: Object, state: true },
    isRecording: { type: Boolean, state: true },
  };

  static styles = [inputStyles];

  constructor() {
    super();
    this.disabled = false;
    this.inputText = '';
    this.previewFile = null;
    this.isRecording = false;
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
    const validTypes = [
      'image/jpeg',
      'image/png',
      'image/gif',
      'image/webp',
      'audio/mpeg',
      'audio/ogg',
      'audio/wav',
      'audio/webm',
      'audio/mp4',
    ];
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

  _openFilePicker() {
    const fileInput = this.shadowRoot.getElementById('media-upload');
    if (fileInput && !this.disabled) {
      fileInput.click();
    }
  }

  _handleVoiceRecordingStarted() {
    this.isRecording = true;
  }

  _handleVoiceRecordingStopped() {
    this.isRecording = false;
  }

  _handleVoiceRecorded(e) {
    this.isRecording = false;
    if (this.disabled) return;

    const file = e.detail?.file;
    if (!file) return;

    this.previewFile = file;
    this.requestUpdate();
  }

  _handleVoiceRecorderError() {
    this.isRecording = false;
  }

  render() {
    const hasText = Boolean(this.inputText.trim());
    const hasAttachment = Boolean(this.previewFile);
    const showSend = !this.isRecording && (hasText || hasAttachment);

    return html`
      <div class="message-input-container">
        ${this.previewFile ? html`
          <media-preview
            .file=${this.previewFile}
            @remove=${this._handleRemoveFile}>
          </media-preview>
        ` : ''}

        <input
          type="file"
          id="media-upload"
          accept="image/*,audio/*"
          @change=${this._handleFileSelect}
          style="display: none;">

        <div class="input-row">
          <textarea
            .value=${this.inputText}
            @input=${this._handleInput}
            @keydown=${this._handleKeyDown}
            placeholder="Type a message..."
            ?disabled=${this.disabled}
            rows="1"></textarea>

          <div class="actions">
            ${showSend ? html`
              <button
                class="send-btn"
                @click=${this._handleSend}
                ?disabled=${this.disabled || (!hasText && !hasAttachment)}>
                Send
              </button>
            ` : html`
              <voice-recorder
                @voice-recording-started=${this._handleVoiceRecordingStarted}
                @voice-recording-stopped=${this._handleVoiceRecordingStopped}
                @voice-recorded=${this._handleVoiceRecorded}
                @voice-recorder-error=${this._handleVoiceRecorderError}
                ?disabled=${this.disabled}>
              </voice-recorder>
              <button
                class="icon-btn attach-btn"
                @click=${this._openFilePicker}
                ?disabled=${this.disabled}
                title="Attach media">
                📎
              </button>
            `}
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('message-input', MessageInput);
