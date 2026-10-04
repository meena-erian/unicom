# Fresh tool output and history limits

`Message.as_llm_chat()` preserves the full text of the tool-response endpoint
and its parallel siblings from the same Request. A continuation needs these
results to decide its next action. Earlier request batches and later user turns
retain the existing size limits and omission/navigation markers.

Freshness is derived from the persisted ToolCall/Request relationship at the
endpoint timestamp, not elapsed time or a mutable “seen” flag. Replaying a
request therefore gets the same fresh results; other branches and future
responses are not made fresh. Legacy responses without a ToolCall relationship
preserve the endpoint itself. Existing multimodal projections remain unchanged.

The previous serializer applied historical limits on first delivery as well,
so a tool could return data the model never received. The regression tests use
oversized parallel outputs, retries, subsequent tool cycles and subsequent user
turns. Existing branch, interruption and Responses adapter tests cover the
surrounding graph and multimodal contracts. No signature or storage migration
is required. Producers should still bound/paginate fresh output for model context
capacity; this policy is history compaction, not a tool-output size validator.
