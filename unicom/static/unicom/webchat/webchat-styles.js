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
    --border-radius: var(--unicom-border-radius, 0px);
    --bubble-radius: var(--unicom-bubble-radius, 16px);
    --control-radius: var(--unicom-control-radius, 12px);
    --media-radius: var(--unicom-media-radius, 12px);
    --scrollbar-track: var(--unicom-scrollbar-track, rgba(0, 0, 0, 0.04));
    --scrollbar-thumb: var(--unicom-scrollbar-thumb, rgba(0, 0, 0, 0.18));
    --sidebar-bg: var(--unicom-sidebar-bg, var(--background-color));
    --sidebar-border-color: var(--unicom-sidebar-border-color, var(--border-color));
    --sidebar-text-color: var(--unicom-sidebar-text-color, var(--text-color));
    --sidebar-secondary-text: var(--unicom-sidebar-secondary-text, var(--secondary-color));
    --sidebar-header-bg: var(--unicom-sidebar-header-bg, var(--primary-color));
    --sidebar-header-text: var(--unicom-sidebar-header-text, #ffffff);
    --sidebar-item-border: var(--unicom-sidebar-item-border, var(--border-color));
    --sidebar-item-hover: var(--unicom-sidebar-item-hover, rgba(0, 0, 0, 0.03));
    --sidebar-item-selected: var(--unicom-sidebar-item-selected, var(--primary-color));
    --sidebar-item-selected-text: var(--unicom-sidebar-item-selected-text, #ffffff);
    --sidebar-item-selected-subtext: var(--unicom-sidebar-item-selected-subtext, rgba(255, 255, 255, 0.8));
    --font-family: var(--unicom-font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
    --input-height: var(--unicom-input-height, 44px);

    display: block;
    width: 100%;
    height: 100%;
    font-family: var(--font-family);
    box-sizing: border-box;
  }

  .unicom-chat-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    max-height: 100%;
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
      container-type: inline-size;
      height: 100%;
      max-height: 100%;
    }
  }

  .unicom-chat-container.dark {
    --background-color: var(--unicom-background-color, #1e1e1e);
    --text-color: var(--unicom-text-color, #ffffff);
    --border-color: var(--unicom-border-color, #444);
    --message-bg-incoming: var(--unicom-message-bg-incoming, #2d2d2d);
    --message-bg-outgoing: var(--unicom-message-bg-outgoing, #0056b3);
    --message-text-incoming: var(--unicom-message-text-incoming, #ffffff);
    --sidebar-bg: var(--unicom-sidebar-bg, #1b1b1b);
    --sidebar-border-color: var(--unicom-sidebar-border-color, #2d2d2d);
    --sidebar-text-color: var(--unicom-sidebar-text-color, #f3f3f3);
    --sidebar-secondary-text: var(--unicom-sidebar-secondary-text, #b0b0b0);
    --sidebar-header-bg: var(--unicom-sidebar-header-bg, #1f1f1f);
    --sidebar-header-text: var(--unicom-sidebar-header-text, #f3f3f3);
    --sidebar-item-border: var(--unicom-sidebar-item-border, rgba(255, 255, 255, 0.08));
    --sidebar-item-hover: rgba(255, 255, 255, 0.08);
    --sidebar-item-selected: var(--primary-color);
    --sidebar-item-selected-text: #ffffff;
    --sidebar-item-selected-subtext: rgba(255, 255, 255, 0.85);
    --scrollbar-track: rgba(255, 255, 255, 0.06);
    --scrollbar-thumb: rgba(255, 255, 255, 0.24);
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
    border-radius: var(--bubble-radius);
    word-wrap: break-word;
    word-break: break-word;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    box-sizing: border-box;
  }

  .message-item.outgoing .message-bubble {
    margin-left: auto;
    background: var(--primary-color);
    color: var(--message-text-outgoing);
    border-bottom-right-radius: clamp(4px, calc(var(--bubble-radius) / 2), var(--bubble-radius));
  }

  .message-item.incoming .message-bubble {
    background: var(--message-bg-incoming);
    color: var(--message-text-incoming);
    border-bottom-left-radius: clamp(4px, calc(var(--bubble-radius) / 2), var(--bubble-radius));
  }

  .message-bubble.media {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: min(100%, 460px);
    max-width: 100%;
  }

  .message-bubble.audio {
    width: min(100%, 520px);
  }

  .message-bubble.media .message-media {
    width: 100%;
  }

  .message-bubble.media .message-timestamp {
    align-self: flex-end;
  }

  .message-item.outgoing .message-bubble.media,
  .message-item.incoming .message-bubble.media {
    max-width: 100%;
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

  .message-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 6px;
    gap: 8px;
  }

  .message-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .branch-navigation {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.8rem;
  }

  .branch-nav-btn {
    background: none;
    border: 1px solid var(--unicom-border-color);
    color: var(--unicom-text-color);
    width: 20px;
    height: 20px;
    border-radius: 3px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    transition: background-color 0.2s;
  }

  .branch-nav-btn:hover:not(:disabled) {
    background-color: var(--unicom-primary-color);
    color: white;
  }

  .branch-nav-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .branch-counter {
    font-size: 0.75rem;
    opacity: 0.7;
    min-width: 30px;
    text-align: center;
  }

  .edit-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 4px;
    font-size: 0.8rem;
    opacity: 0.6;
    transition: opacity 0.2s, background-color 0.2s;
  }

  .edit-btn:hover {
    opacity: 1;
    background-color: rgba(0, 0, 0, 0.1);
  }

  .dark .edit-btn:hover {
    background-color: rgba(255, 255, 255, 0.1);
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
    border-radius: var(--media-radius);
    cursor: pointer;
    display: block;
  }

  .message-media audio {
    width: 100%;
    max-width: 100%;
    display: block;
    margin-top: 4px;
    border-radius: var(--control-radius);
    background: rgba(0, 0, 0, 0.05);
  }

  .dark .message-media audio {
    background: rgba(255, 255, 255, 0.1);
  }

  .message-system {
    font-style: italic;
    opacity: 0.8;
    font-size: 0.9em;
  }

  .tool-status {
    font-size: 0.85em;
    opacity: 0.7;
    display: flex;
    align-items: center;
    gap: 0.5em;
    padding: 0.25em 0;
    color: var(--message-text-incoming, #212529);
  }

  .tool-icon {
    font-size: 0.9em;
  }

  .loading-dots {
    animation: loading-dots 1.5s infinite;
  }

  @keyframes loading-dots {
    0%, 20% { content: ''; }
    40% { content: '.'; }
    60% { content: '..'; }
    80%, 100% { content: '...'; }
  }

  @container (max-width: 768px) {
    .message-bubble {
      max-width: calc(100% - 24px);
    }
  }

  /* Interactive Buttons - Telegram-style positioning and theming */
  .interactive-buttons {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 100%;
    max-width: calc(100% - 32px);
  }

  .message-item.outgoing .interactive-buttons {
    align-self: flex-end;
    margin-left: auto;
  }

  .message-item.incoming .interactive-buttons {
    align-self: flex-start;
    margin-right: auto;
  }

  .button-row {
    display: flex;
    gap: 6px;
    width: 100%;
  }

  .interactive-btn {
    padding: 12px 16px;
    border: none;
    border-radius: var(--bubble-radius);
    cursor: pointer;
    font-size: inherit;
    font-weight: inherit;
    font-family: inherit;
    transition: all 0.15s ease;
    flex: 1;
    min-height: 44px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    word-wrap: break-word;
    word-break: break-word;
    box-sizing: border-box;
  }

  /* Use exact message bubble colors and styling */
  .message-item.outgoing .interactive-btn {
    background: var(--primary-color);
    color: var(--message-text-outgoing);
    border-bottom-right-radius: clamp(4px, calc(var(--bubble-radius) / 2), var(--bubble-radius));
  }

  .message-item.incoming .interactive-btn {
    background: var(--message-bg-incoming);
    color: var(--message-text-incoming);
    border-bottom-left-radius: clamp(4px, calc(var(--bubble-radius) / 2), var(--bubble-radius));
  }

  .interactive-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
  }

  .interactive-btn:active:not(:disabled) {
    transform: translateY(0);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  }

  .interactive-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }

  /* Responsive button sizing */
  @container (max-width: 768px) {
    .interactive-buttons {
      max-width: calc(100% - 24px);
      align-self: center !important;
      margin-left: auto;
      margin-right: auto;
    }
  }

  /* Desktop: Match message bubble width */
  @container (min-width: 769px) {
    .interactive-buttons {
      max-width: min(calc(100% - 32px), 460px);
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
    align-items: flex-end;
    gap: 12px;
  }

  .edit-mode-indicator {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: rgba(255, 193, 7, 0.1);
    border-left: 3px solid #ffc107;
    font-size: 0.9em;
    color: #856404;
  }

  .dark .edit-mode-indicator {
    background: rgba(255, 193, 7, 0.2);
    color: #fff3cd;
  }

  .cancel-edit-btn {
    background: none;
    border: 1px solid #ffc107;
    color: #856404;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8em;
    transition: background-color 0.2s;
  }

  .cancel-edit-btn:hover {
    background-color: rgba(255, 193, 7, 0.1);
  }

  .dark .cancel-edit-btn {
    color: #fff3cd;
    border-color: #fff3cd;
  }

  .dark .cancel-edit-btn:hover {
    background-color: rgba(255, 193, 7, 0.2);
  }

  .input-row textarea {
    flex: 1;
    padding: 10px 12px;
    min-height: var(--input-height);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    font-family: inherit;
    font-size: 0.95em;
    resize: none;
    max-height: 160px;
    background: var(--background-color);
    color: var(--text-color);
    overflow-y: auto;
    line-height: 1.35;
    box-sizing: border-box;
  }

  .input-row textarea:focus {
    outline: none;
    border-color: var(--primary-color);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
  }

  .icon-btn,
  .send-btn {
    flex-shrink: 0;
    height: var(--input-height);
    border-radius: var(--control-radius);
    border: 1px solid var(--border-color);
    background: var(--background-color);
    color: var(--text-color);
    font-size: 0.95em;
    font-weight: 500;
    padding: 0 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .icon-btn {
    width: var(--input-height);
    padding: 0;
    font-size: 1.2em;
  }

  .send-btn {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: #fff;
    font-weight: 600;
    padding: 0 20px;
  }

  .icon-btn:hover:not(:disabled),
  .send-btn:hover:not(:disabled) {
    transform: translateY(-1px);
  }

  .icon-btn:disabled,
  .send-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .dark textarea,
  .dark .icon-btn,
  .dark .send-btn {
    background: #2d2d2d;
    border-color: #444;
    color: #fff;
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
    scrollbar-width: thin;
    scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
  }

  .message-list::-webkit-scrollbar {
    width: 8px;
  }

  .message-list::-webkit-scrollbar-track {
    background: var(--scrollbar-track);
  }

  .message-list::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: 999px;
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
    border-radius: var(--control-radius);
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
    border-radius: var(--control-radius);
    padding: 8px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .media-preview.audio {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .preview-thumbnail {
    width: 60px;
    height: 60px;
    object-fit: cover;
    border-radius: var(--media-radius);
  }

  .preview-thumbnail.icon {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5em;
    background: var(--border-color);
  }

  .preview-audio-container {
    width: 100%;
  }

  .preview-audio {
    width: 100%;
    display: block;
    border-radius: var(--control-radius);
    background: rgba(0, 0, 0, 0.05);
  }

  .dark .preview-audio {
    background: rgba(255, 255, 255, 0.1);
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

  .media-preview.audio .preview-remove {
    align-self: flex-end;
  }

  .preview-remove:hover {
    color: #dc3545;
  }
`;
