/**
 * Media Preview Component
 * Shows preview of selected file before sending
 */
import { LitElement, html, css } from 'lit';
import { iconStyles, previewStyles } from '../webchat-styles.js';
import fontAwesomeLoader from '../utils/font-awesome-loader.js';

export class MediaPreview extends LitElement {
  static properties = {
    file: { type: Object },
    progress: { type: Number },
    uploading: { type: Boolean },
  };

  static styles = [iconStyles, previewStyles];

  constructor() {
    super();
    this.file = null;
    this.progress = null;
    this.uploading = false;
    this._objectUrl = null;
  }

  async firstUpdated() {
    await fontAwesomeLoader.applyToShadowRoot(this.shadowRoot);
  }

  updated(changedProps) {
    if (changedProps.has('file')) {
      if (this._objectUrl) {
        URL.revokeObjectURL(this._objectUrl);
        this._objectUrl = null;
      }
      if (this.file) {
        this._objectUrl = URL.createObjectURL(this.file);
      }
    }
  }

  _formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  _handleRemove() {
    this.dispatchEvent(new CustomEvent('remove', {
      bubbles: true,
      composed: true,
    }));
  }

  render() {
    if (!this.file) return html``;

    const type = this.file.type || '';
    const isImage = type.startsWith('image/');
    const isAudio = type.startsWith('audio/');
    const previewUrl = this._objectUrl;
    const progress = Number.isFinite(this.progress) ? this.progress : 0;
    const extension = (this.file.name.split('.').pop() || 'FILE').slice(0, 5).toUpperCase();

    return html`
      <div class="media-preview ${isAudio ? 'audio' : ''}">
        ${isImage && previewUrl ? html`
          <img class="preview-thumbnail" src="${previewUrl}" alt="Preview">
        ` : html`
          <div class="preview-thumbnail icon">
            <i class="fa-solid ${isAudio ? 'fa-file-audio' : 'fa-file'}" aria-hidden="true"></i>
          </div>
        `}
        <div class="preview-info">
          <div class="preview-filename">${this.file.name}</div>
          <div class="preview-meta">
            <span>${extension}</span><span aria-hidden="true">·</span>
            <span>${this._formatFileSize(this.file.size)}</span><span aria-hidden="true">·</span>
            <span>${this.uploading ? `${progress}%` : 'Ready'}</span>
          </div>
          <div class="preview-progress" aria-label=${this.uploading ? `Upload ${progress}%` : 'Ready to upload'}>
            <span style=${`width:${this.uploading ? progress : 0}%`}></span>
          </div>
        </div>
        <button class="preview-remove" @click=${this._handleRemove} ?disabled=${this.uploading} title="Remove file" aria-label="Remove attachment">
          <i class="fa-solid fa-xmark" aria-hidden="true"></i>
        </button>
      </div>
    `;
  }

  disconnectedCallback() {
    if (this._objectUrl) {
      URL.revokeObjectURL(this._objectUrl);
      this._objectUrl = null;
    }
    super.disconnectedCallback();
  }
}

customElements.define('media-preview', MediaPreview);
