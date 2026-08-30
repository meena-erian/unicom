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
    disabled: { type: Boolean },
    editingMessageId: { type: String, attribute: 'editing-message-id' },
    sending: { type: Boolean },
    sendAck: { type: Number },
    inputText: { type: String, state: true },
    previewFile: { type: Object, state: true },
    isRecording: { type: Boolean, state: true },
    expanded: { type: Boolean, state: true },
    dragActive: { type: Boolean, state: true },
    uploadProgress: { type: Number, attribute: false },
    attachmentUploading: { type: Boolean, attribute: false },
    stagedUploadToken: { type: String, attribute: false },
    emptyPrompt: { type: String, attribute: 'empty-prompt' },
  };

  static styles = [iconStyles, inputStyles];

  constructor() {
    super();
    this.disabled = false;
    this.sending = false;
    this.sendAck = 0;
    this.editingMessageId = null;
    this.inputText = '';
    this.previewFile = null;
    this.isRecording = false;
    this.expanded = false;
    this.dragActive = false;
    this._dragDepth = 0;
    this.uploadProgress = null;
    this.attachmentUploading = false;
    this.stagedUploadToken = null;
    this.emptyPrompt = '';
  }

  async firstUpdated() {
    await fontAwesomeLoader.applyToShadowRoot(this.shadowRoot);
  }

  _handleInput(e) {
    this.inputText = e.target.value;
    this._resizeTextarea(e.target);
  }

  _resizeTextarea(textarea) {
    if (!textarea) return;
    textarea.style.height = 'auto';
    const row = this.shadowRoot.querySelector('.composer-row');
    const compactTextWidth = Math.max(40, (row?.clientWidth || textarea.clientWidth + 96) - 96);
    const compactProbe = textarea.cloneNode();
    compactProbe.value = textarea.value;
    compactProbe.style.cssText = `position:fixed;visibility:hidden;pointer-events:none;width:${compactTextWidth}px;height:auto;inset:auto;`;
    row?.appendChild(compactProbe);
    const compactHasWrapped = textarea.value.includes('\n') || compactProbe.scrollHeight > 40;
    compactProbe.remove();
    const needsFullWidth = compactHasWrapped;
    if (this.expanded !== needsFullWidth) {
      this.expanded = needsFullWidth;
      return;
    }
    if (!this.expanded) {
      textarea.style.height = '36px';
      textarea.style.overflowY = 'hidden';
      return;
    }
    const maxHeight = Math.max(120, Math.floor(window.innerHeight * 0.42));
    const nextHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden';
  }

  _handleKeyDown(e) {
    const isCompactLayout = window.matchMedia('(max-width: 768px)').matches;
    if (e.key === 'Enter' && !e.shiftKey && !isCompactLayout && !e.isComposing) {
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
        file: this.stagedUploadToken ? null : this.previewFile,
        stagedUploadToken: this.stagedUploadToken,
        replyToMessageId: this.editingMessageId, // Include for editing/branching
      },
      bubbles: true,
      composed: true,
    }));
  }

  _handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) this.attachFile(file);
    // Clear the input so the same file can be selected again
    e.target.value = '';
  }

  attachFile(file) {
    if (!file || this.disabled || this.sending) return false;

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
      return false;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB');
      return false;
    }

    this.previewFile = file;
    this.dispatchEvent(new CustomEvent('attachment-selected', {
      detail: { file }, bubbles: true, composed: true,
    }));
    return true;
  }

  _handlePaste(e) {
    const file = Array.from(e.clipboardData?.files || [])[0];
    if (file && this.attachFile(file)) {
      e.preventDefault();
    }
  }

  _hasDraggedFiles(e) {
    return Array.from(e.dataTransfer?.types || []).includes('Files');
  }

  _handleDragEnter(e) {
    if (!this._hasDraggedFiles(e) || this.disabled || this.sending) return;
    e.preventDefault();
    this._dragDepth += 1;
    this.dragActive = true;
  }

  _handleDragOver(e) {
    if (!this._hasDraggedFiles(e) || this.disabled || this.sending) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  }

  _handleDragLeave(e) {
    if (!this._hasDraggedFiles(e)) return;
    e.preventDefault();
    this._dragDepth = Math.max(0, this._dragDepth - 1);
    if (this._dragDepth === 0) this.dragActive = false;
  }

  _handleDrop(e) {
    if (!this._hasDraggedFiles(e)) return;
    e.preventDefault();
    this._dragDepth = 0;
    this.dragActive = false;
    const file = Array.from(e.dataTransfer?.files || [])[0];
    if (file) this.attachFile(file);
  }

  _handleRemoveFile() {
    this.previewFile = null;
    this.dispatchEvent(new CustomEvent('attachment-removed', {
      bubbles: true, composed: true,
    }));
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

    this.previewFile = file;
    this.requestUpdate();
  }

  _handleVoiceRecorderError() {
    this.isRecording = false;
  }

  updated(changed) {
    if (changed.has('sendAck') && changed.get('sendAck') !== this.sendAck) {
      this._clearInput();
    }
    if (changed.has('expanded')) {
      this._resizeTextarea(this.shadowRoot.querySelector('textarea'));
    }
  }

  _clearInput() {
    this.inputText = '';
    this.previewFile = null;
    this.editingMessageId = null;
    this.expanded = false;
    const textarea = this.shadowRoot.querySelector('textarea');
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.overflowY = 'hidden';
    }
  }

  _handleCancelEdit() {
    this.editingMessageId = null;
    this.inputText = '';
    this.previewFile = null;
    this.expanded = false;
    
    // Reset textarea height
    const textarea = this.shadowRoot.querySelector('textarea');
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.overflowY = 'hidden';
    }
  }

  render() {
    const hasText = Boolean(this.inputText.trim());
    const hasAttachment = Boolean(this.previewFile);
    const showSend = !this.isRecording && (hasText || hasAttachment);
    const isEditing = Boolean(this.editingMessageId);
    const isDisabled = this.disabled || this.sending || this.attachmentUploading;

    return html`
      ${this.emptyPrompt ? html`
        <div class="empty-prompt">${this.emptyPrompt}</div>
      ` : ''}
      <div class="message-input-container">
        <input
          type="file"
          id="media-upload"
          accept="image/*,audio/*"
          @change=${this._handleFileSelect}
          style="display: none;">

        <div
          class="composer-shell ${isEditing ? 'editing' : ''} ${this.dragActive ? 'drag-active' : ''}"
          @dragenter=${this._handleDragEnter}
          @dragover=${this._handleDragOver}
          @dragleave=${this._handleDragLeave}
          @drop=${this._handleDrop}>
        ${isEditing ? html`
          <div class="edit-mode-indicator">
            <span>
              <i class="fa-solid fa-pen" aria-hidden="true"></i>
              <span>Editing message</span>
            </span>
            <button class="cancel-edit-btn" @click=${this._handleCancelEdit}>Cancel</button>
          </div>
        ` : ''}

        ${this.previewFile ? html`
          <media-preview
            .file=${this.previewFile}
            .progress=${this.uploadProgress}
            .uploading=${this.attachmentUploading}
            .uploaded=${Boolean(this.stagedUploadToken)}
            @remove=${this._handleRemoveFile}>
          </media-preview>
        ` : ''}

          <div class="composer-row ${this.expanded ? 'expanded' : ''}">
            <button
              class="composer-icon-btn attach-btn"
              @click=${this._openFilePicker}
              ?disabled=${isDisabled}
              title="Attach media"
              aria-label="Attach media">
              <i class="fa-solid fa-paperclip" aria-hidden="true"></i>
            </button>
            ${this.isRecording ? html`<span class="recording-spacer"></span>` : html`
            <textarea
              .value=${this.inputText}
              @input=${this._handleInput}
              @paste=${this._handlePaste}
              @keydown=${this._handleKeyDown}
              placeholder=${isEditing ? "Edit your message..." : "Type a message..."}
              ?disabled=${isDisabled}
              rows="1"></textarea>
            `}
            <div class="composer-primary-action">
              ${showSend ? html`
                <button
                  class="send-btn"
                  @click=${this._handleSend}
                  ?disabled=${isDisabled || (!hasText && !hasAttachment)}
                  title=${isEditing ? 'Update message' : 'Send message'}
                  aria-label=${isEditing ? 'Update message' : 'Send message'}>
                  ${this.sending
                    ? html`<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i>`
                    : html`<i class="fa-solid fa-arrow-up" aria-hidden="true"></i>`}
                </button>
              ` : html`
                <voice-recorder
                  @voice-recording-started=${this._handleVoiceRecordingStarted}
                  @voice-recording-stopped=${this._handleVoiceRecordingStopped}
                  @voice-recorded=${this._handleVoiceRecorded}
                  @voice-recorder-error=${this._handleVoiceRecorderError}
                  ?disabled=${isDisabled}>
                </voice-recorder>
              `}
            </div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('message-input', MessageInput);
