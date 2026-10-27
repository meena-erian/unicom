# Shared WebChat loading presentation

Both native chat variants use the same skeleton through their message-list and chat-list components. It appears only while an empty list is loading. Refreshing a populated list preserves its nodes and layout; `aria-busy` still communicates background loading. Sending, polling, history pagination and API contracts are unchanged.

The skeleton has a narrow glare that crosses the placeholders on a slow four-second cycle. Reduced-motion users receive static placeholders. Forced-colors mode uses visible outlines. Customize `--unicom-skeleton-fill` and `--unicom-skeleton-glare` if needed; the defaults inherit existing chat background/border theme variables.

For Django hosts that lazy-load chat JavaScript, render the same shared stylesheet and skeleton before the component is ready:

```django
{% include 'unicom/webchat/loading_skeleton.html' %}
```

Place it in a positioned chat container. The default element ID is `chat-loading`; pass `skeleton_id` for multiple instances. Hide it after the initial load and keep it hidden during background refreshes. Do not bind a full-chat cover to every `loadingChats` change: sidebar previews refresh after incoming messages and stream completion, which otherwise repeatedly covers a usable conversation. UniStack implements this initial-only behavior.

The module helper `components/loading-skeleton.js` and Django include consume one CSS file, `loading-skeleton.css`. No app-specific text, model behavior or authentication changes are included. Existing deployments must update their pinned UniCom version and collect/redeploy static files to receive the change.

Validation: `python tests/test_webchat_loading_browser.py` checks empty-list loading, unchanged DOM and layout during repeated populated-list refreshes, animation timing, and reduced-motion behavior in Chromium. `node --test static/unicom/webchat/utils/streaming-text-controller.test.mjs` checks streamed text regressions.
