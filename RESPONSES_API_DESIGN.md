# Optional Responses API Mode

## Goal

Add general-purpose OpenAI Responses API support without changing existing
Unicom projects. This is not Codex-specific.

## Public API

Add an opt-in argument to the LLM entry points:

```python
api_mode: Literal["chat_completions", "responses"] = "chat_completions"
```

Expose it on `Bot.reply_using_llm()` and `Message.reply_using_llm()`. A bot may
also persist this as its default. Omitting the argument must execute the current
Chat Completions implementation unchanged.

## Implementation Boundary

Keep the current Chat Completions handler as-is. Add a sibling Responses
adapter/handler selected only when `api_mode="responses"`.

The Responses handler translates:

- Unicom history into Responses `instructions` and `input` items.
- Unicom tool schemas into Responses function-tool schemas.
- Responses text, usage, and function-call output into a normalized internal
  result consumed by the existing reply and tool-call lifecycle.

The existing `Request.submit_tool_calls()`, tool execution, persisted
`tool_call`/`tool_response` messages, and child-request workflow remain the
source of truth. On the next model call, the adapter converts persisted calls
and results to Responses `function_call` and `function_call_output` items,
preserving each `call_id`.

## Compatibility

Text and function calling are supported by the adapter. Streaming is optional
and should not be required for the initial implementation.

Responses mode must validate requested modalities against the selected model:

- Text is required.
- Image input/output support is model-specific.
- Audio input/output support is model-specific.

Do not silently send unsupported media. Raise a clear capability error or use a
caller-selected fallback. API mode does not itself imply that a model supports
audio, images, image generation, web search, or other hosted tools.

## Non-Goals

- Do not add a Chat Completions compatibility endpoint to a Responses provider.
- Do not change defaults, existing request history, or existing bot behavior.
- Do not make provider-specific authentication part of Unicom. Applications
  continue to construct and pass their own OpenAI-compatible client.

## Tests

Add isolated Responses-mode tests for text replies, function-call extraction,
function-call output continuation, image input conversion, unsupported audio,
and unchanged default Chat Completions behavior.
