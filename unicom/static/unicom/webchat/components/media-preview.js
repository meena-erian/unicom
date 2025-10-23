/**
 * Media Preview Component
 * Shows preview of selected file before sending
 */
import { LitElement, html, css } from 'lit';
import { previewStyles } from '../webchat-styles.js';

export class MediaPreview extends LitElement {
  static properties = {
    file: { type: Object },
  };

  static styles = [previewStyles];

  constructor() {
    super();
    this.file = null;
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

    const isImage = this.file.type.startsWith('image/');
    const previewUrl = isImage ? URL.createObjectURL(this.file) : null;

    return html`
      <div class="media-preview">
        ${isImage ? html`
          <img class="preview-thumbnail" src="${previewUrl}" alt="Preview">
        ` : html`
          <div class="preview-thumbnail" style="display: flex; align-items: center; justify-content: center; background: var(--border-color);">
            🎵
          </div>
        `}
        <div class="preview-info">
          <div class="preview-filename">${this.file.name}</div>
          <div class="preview-filesize">${this._formatFileSize(this.file.size)}</div>
        </div>
        <button class="preview-remove" @click=${this._handleRemove} title="Remove file">
          ✕
        </button>
      </div>
    `;
  }
}

customElements.define('media-preview', MediaPreview);
