/**
 * Message Input Component
 * Textarea, send button, and media upload
 */
import { LitElement, html } from 'lit';
import { iconStyles, inputStyles } from '../webchat-styles.js';
import fontAwesomeLoader from '../utils/font-awesome-loader.js';
import './media-preview.js';
import './voice-recorder.js';

export class MessageInput extends LitElement {
  static properties = {
    maxAttachments: { type: Number, attribute: 'max-attachments' },
    selectedFiles: { type: Array, state: true },
    disabled: { type: Boolean },
    editingMessageId: { type: String, attribute: 'editing-message-id' },
    sending: { type: Boolean },
    sendAck: { type: Number },
    inputText: { type: String, state: true },
    previewFile: { type: Object, state: true },
    isRecording: { type: Boolean, state: true },
  };

  static styles = [iconStyles, inputStyles];

  constructor() {
    super();
    this.maxAttachments = 1;
    this.selectedFiles = [];
    this.disabled = false;
    this.sending = false;
    this.sendAck = 0;
    this.editingMessageId = null;
    this.inputText = '';
    this.previewFile = null;
    this.isRecording = false;
  }

  async firstUpdated() {
    await fontAwesomeLoader.applyToShadowRoot(this.shadowRoot);
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
    if (this.disabled || this.sending) return;

    const text = this.inputText.trim();
    if (!text && !this.previewFile) return;

    this.dispatchEvent(new CustomEvent('send-message', {
      detail: {
        text: text,
        file: this.previewFile,
        files: this.selectedFiles,
        replyToMessageId: this.editingMessageId, // Include for editing/branching
      },
      bubbles: true,
      composed: true,
    }));
  }

  _handleFileSelect(e) {
    this.attachFiles(Array.from(e.target.files || []));
    e.target.value = '';
  }

  attachFiles(files) {
    if (this.disabled || this.sending) return;
    const next = this.maxAttachments === 1 ? files : [...this.selectedFiles, ...files];
    if (next.length > this.maxAttachments) {
      alert(`Select at most ${this.maxAttachments} attachments`);
      return;
    }
    const supported = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/webm', 'audio/mp4'];
    if (files.some(file => file.size > 10 * 1024 * 1024 || !supported.includes(file.type))) {
      alert('Select image or audio files no larger than 10MB');
      return;
    }
    this.selectedFiles = next;
    this.previewFile = next[0] || null;
  }

  _handleDrop(event) {
    if (!Array.from(event.dataTransfer?.types || []).includes('Files')) return;
    event.preventDefault();
    this.attachFiles(Array.from(event.dataTransfer.files));
  }

  _handleDragOver(event) {
    if (Array.from(event.dataTransfer?.types || []).includes('Files')) event.preventDefault();
  }

  _handleRemoveFile(file) {
    this.selectedFiles = this.selectedFiles.filter(item => item !== file);
    this.previewFile = this.selectedFiles[0] || null;
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
    if (this.disabled || this.sending) return;

    const file = e.detail?.file;
    if (!file) return;

    this.attachFiles([file]);
    this.requestUpdate();
  }

  _handleVoiceRecorderError() {
    this.isRecording = false;
  }

  updated(changed) {
    if (changed.has('sendAck') && changed.get('sendAck') !== this.sendAck) {
      this._clearInput();
    }
  }

  _clearInput() {
    this.selectedFiles = [];
    this.inputText = '';
    this.previewFile = null;
    this.editingMessageId = null;
    const textarea = this.shadowRoot.querySelector('textarea');
    if (textarea) {
      textarea.style.height = 'auto';
    }
  }

  _handleCancelEdit() {
    this.selectedFiles = [];
    this.editingMessageId = null;
    this.inputText = '';
    this.previewFile = null;
    
    // Reset textarea height
    const textarea = this.shadowRoot.querySelector('textarea');
    if (textarea) {
      textarea.style.height = 'auto';
    }
  }

  render() {
    const hasText = Boolean(this.inputText.trim());
    const hasAttachment = Boolean(this.previewFile);
    const showSend = !this.isRecording && (hasText || hasAttachment);
    const isEditing = Boolean(this.editingMessageId);
    const isDisabled = this.disabled || this.sending;

    return html`
      <div class="message-input-container" @drop=${this._handleDrop} @dragover=${this._handleDragOver}>
        ${isEditing ? html`
          <div class="edit-mode-indicator">
            <span>
              <i class="fa-solid fa-pen" aria-hidden="true"></i>
              <span>Editing message</span>
            </span>
            <button class="cancel-edit-btn" @click=${this._handleCancelEdit}>Cancel</button>
          </div>
        ` : ''}

        ${this.selectedFiles.map(file => html`
          <media-preview
            .file=${file}
            @remove=${() => this._handleRemoveFile(file)}>
          </media-preview>
        `)}

        <input
          type="file"
          id="media-upload"
          accept="image/*,audio/*"
          ?multiple=${this.maxAttachments > 1}
          @change=${this._handleFileSelect}
          style="display: none;">

        <div class="input-row">
          ${this.isRecording ? html`` : html`
            <textarea
              .value=${this.inputText}
              @input=${this._handleInput}
              @keydown=${this._handleKeyDown}
              placeholder=${isEditing ? "Edit your message..." : "Type a message..."}
              ?disabled=${isDisabled}
              rows="1"></textarea>
          `}

          <div class="actions">
            ${showSend && this.maxAttachments > 1 ? html`<button type="button" class="icon-btn attach-btn" @click=${this._openFilePicker} ?disabled=${isDisabled} aria-label="Attach more files"><i class="fa-solid fa-paperclip" aria-hidden="true"></i></button>` : ''}
            ${showSend ? html`
              <button
                class="send-btn"
                @click=${this._handleSend}
                ?disabled=${isDisabled || (!hasText && !hasAttachment)}>
                ${this.sending ? 'Sending…' : (isEditing ? 'Update' : 'Send')}
              </button>
            ` : html`
              <voice-recorder
                @voice-recording-started=${this._handleVoiceRecordingStarted}
                @voice-recording-stopped=${this._handleVoiceRecordingStopped}
                @voice-recorded=${this._handleVoiceRecorded}
                @voice-recorder-error=${this._handleVoiceRecorderError}
                ?disabled=${isDisabled}>
              </voice-recorder>
              <button
                class="icon-btn attach-btn"
                @click=${this._openFilePicker}
                ?disabled=${isDisabled}
                title="Attach media">
                <i class="fa-solid fa-paperclip" aria-hidden="true"></i>
              </button>
            `}
          </div>
          ${this.sending ? html`
            <div class="sending-indicator">
              <i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i>
              <span>Sending…</span>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }
}

customElements.define('message-input', MessageInput);
