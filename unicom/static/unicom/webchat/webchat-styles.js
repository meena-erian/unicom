/**
 * Shared styles for WebChat components
 */
import { css } from 'lit';

export const baseStyles = css`
  :host {
    /* CSS custom properties for theming */
    --primary-color: var(--unicom-primary-color, #007bff);
    --secondary-color: var(--unicom-secondary-color, #6c757d);
    --background-color: var(--unicom-background-color, #ffffff);
    --message-bg-incoming: var(--unicom-message-bg-incoming, #f1f3f4);
    --message-bg-outgoing: var(--unicom-message-bg-outgoing, #007bff);
    --message-text-incoming: var(--unicom-message-text-incoming, #212529);
    --message-text-outgoing: var(--unicom-message-text-outgoing, #ffffff);
    --text-color: var(--unicom-text-color, #212529);
    --border-color: var(--unicom-border-color, #dee2e6);
    --border-radius: var(--unicom-border-radius, 8px);
    --font-family: var(--unicom-font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
    --input-height: var(--unicom-input-height, 44px);
    --max-width: var(--unicom-max-width, 800px);

    display: block;
    width: 100%;
    font-family: var(--font-family);
    max-width: var(--max-width);
    margin: 0 auto;
  }

  .unicom-chat-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: min(var(--unicom-container-height, 600px), 100vh);
    max-height: min(var(--unicom-container-height, 600px), 100vh);
    min-height: 0;
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    background: var(--background-color);
    overflow: hidden;
    position: relative;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    box-sizing: border-box;
    padding-left: env(safe-area-inset-left, 0px);
    padding-right: env(safe-area-inset-right, 0px);
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }

  @supports (height: 100dvh) {
    .unicom-chat-container {
      height: min(var(--unicom-container-height, 600px), 100dvh);
      max-height: min(var(--unicom-container-height, 600px), 100dvh);
    }
  }

  .unicom-chat-container.dark {
    --background-color: #1e1e1e;
    --text-color: #ffffff;
    --border-color: #444;
    --message-bg-incoming: #2d2d2d;
    --message-bg-outgoing: #0056b3;
    --message-text-incoming: #ffffff;
  }

  .error-banner {
    background-color: #f8d7da;
    color: #721c24;
    padding: 12px;
    border-bottom: 1px solid #f5c6cb;
    text-align: center;
    font-size: 0.9em;
  }

  .dark .error-banner {
    background-color: #5a1a1a;
    color: #f8d7da;
    border-bottom-color: #721c24;
  }
`;

export const messageStyles = css`
  .message-item {
    padding: 8px 8px;
    display: flex;
    flex-direction: column;
    width: 100%;
    animation: fadeIn 0.3s ease-in;
    box-sizing: border-box;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .message-item.outgoing {
    align-items: flex-end;
  }

  .message-item.incoming {
    align-items: flex-start;
  }

  .sender-name {
    font-size: 0.8rem;
    color: var(--secondary-color);
    margin-bottom: 4px;
    font-weight: 500;
  }

  .message-bubble {
    display: inline-block;
    max-width: calc(100% - 32px);
    padding: 12px 16px;
    border-radius: var(--border-radius);
    word-wrap: break-word;
    word-break: break-word;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    box-sizing: border-box;
  }

  .message-item.outgoing .message-bubble {
    margin-left: auto;
    background: var(--message-bg-outgoing);
    color: var(--message-text-outgoing);
    border-bottom-right-radius: 4px;
  }

  .message-item.incoming .message-bubble {
    background: var(--message-bg-incoming);
    color: var(--message-text-incoming);
    border-bottom-left-radius: 4px;
  }

  .message-text {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .message-html {
    margin: 0;
  }

  .message-html * {
    max-width: 100%;
  }

  .message-timestamp {
    font-size: 0.7rem;
    opacity: 0.7;
    margin-top: 6px;
  }

  .message-media {
    margin: 0;
  }

  .message-caption {
    margin-bottom: 8px;
    font-size: 0.9em;
  }

  .message-media img {
    max-width: 100%;
    max-height: 400px;
    border-radius: 8px;
    cursor: pointer;
    display: block;
  }

  .message-media audio {
    width: 100%;
    max-width: 300px;
  }

  .message-system {
    font-style: italic;
    opacity: 0.8;
    font-size: 0.9em;
  }

  @media (max-width: 768px) {
    .message-bubble {
      max-width: calc(100% - 24px);
    }
  }
`;

export const inputStyles = css`
  :host {
    display: block;
    flex-shrink: 0;
  }

  .message-input-container {
    border-top: 1px solid var(--border-color);
    background: var(--background-color);
    padding: 12px;
    box-sizing: border-box;
  }

  .input-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .attach-btn,
  .send-btn {
    flex-shrink: 0;
    height: var(--input-height);
    padding: 0 16px;
    border: none;
    border-radius: var(--border-radius);
    cursor: pointer;
    font-size: 0.95em;
    font-weight: 500;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .attach-btn {
    background: transparent;
    color: var(--secondary-color);
    font-size: 1.2em;
    padding: 8px 12px;
  }

  .attach-btn:hover:not(:disabled) {
    background: var(--message-bg-incoming);
  }

  .send-btn {
    background: var(--primary-color);
    color: white;
  }

  .send-btn:hover:not(:disabled) {
    opacity: 0.9;
    transform: translateY(-1px);
  }

  .send-btn:disabled,
  .attach-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  textarea {
    flex: 1;
    padding: 10px 12px;
    min-height: var(--input-height);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    font-family: inherit;
    font-size: 0.95em;
    resize: none;
    max-height: 120px;
    background: var(--background-color);
    color: var(--text-color);
    overflow-y: auto;
    line-height: 1.35;
    box-sizing: border-box;
  }

  textarea:focus {
    outline: none;
    border-color: var(--primary-color);
  }

  .dark textarea {
    background: #2d2d2d;
    border-color: #444;
  }
`;

export const listStyles = css`
  :host {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    width: 100%;
  }

  .message-list {
    flex: 1 1 auto;
    overflow-y: auto;
    overflow-x: hidden;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 0;
    -webkit-overflow-scrolling: touch;
    box-sizing: border-box;
  }

  .loading-spinner {
    text-align: center;
    padding: 20px;
    color: var(--secondary-color);
  }

  .loading-spinner::after {
    content: '⏳';
    animation: spin 1s linear infinite;
    display: inline-block;
    font-size: 1.5em;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  .load-more-btn {
    background: var(--message-bg-incoming);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    padding: 8px 16px;
    cursor: pointer;
    font-size: 0.9em;
    margin: 0 auto 16px;
    transition: background 0.2s ease;
  }

  .load-more-btn:hover {
    background: var(--border-color);
  }

  .empty-state {
    text-align: center;
    padding: 40px 20px;
    color: var(--secondary-color);
  }

  .empty-state-icon {
    font-size: 3em;
    margin-bottom: 16px;
    opacity: 0.5;
  }
`;

export const previewStyles = css`
  .media-preview {
    background: var(--message-bg-incoming);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    padding: 8px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .preview-thumbnail {
    width: 60px;
    height: 60px;
    object-fit: cover;
    border-radius: 4px;
  }

  .preview-info {
    flex: 1;
    font-size: 0.9em;
  }

  .preview-filename {
    font-weight: 500;
    margin-bottom: 4px;
    color: var(--text-color);
  }

  .preview-filesize {
    color: var(--secondary-color);
    font-size: 0.85em;
  }

  .preview-remove {
    background: transparent;
    border: none;
    color: var(--secondary-color);
    cursor: pointer;
    font-size: 1.2em;
    padding: 4px 8px;
  }

  .preview-remove:hover {
    color: #dc3545;
  }
`;
