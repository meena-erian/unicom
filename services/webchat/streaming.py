"""Durable WebChat projection for provider streaming events."""

from __future__ import annotations

import time


class WebChatMessageStreamSink:
    """Project provider events onto one durable outgoing WebChat message.

    The sink is deliberately provider-neutral. Callers emit ``started``,
    ``text.delta``, ``finished`` and ``failed`` events. The final message is the
    durable chat record; intermediate saves are only a live projection.
    """

    def __init__(self, source_message, flush_interval=0.075):
        if source_message.platform != "WebChat":
            raise ValueError("WebChatMessageStreamSink requires a WebChat message")
        self.source_message = source_message
        self.flush_interval = max(0, flush_interval)
        self.message = None
        self.text = ""
        self._last_flush = 0.0

    def __call__(self, event):
        event_type = event.get("type")
        if event_type == "started":
            return self._start(event)
        if event_type == "text.delta":
            return self._delta(event.get("delta", ""))
        if event_type == "finished":
            return self._finish(event)
        if event_type == "failed":
            return self._fail(event)
        raise ValueError(f"Unsupported stream event type: {event_type}")

    def _stream_metadata(self, status, event=None):
        metadata = {
            "status": status,
            "response_id": (event or {}).get("response_id"),
        }
        if event and event.get("error"):
            metadata["error"] = str(event["error"])
        return metadata

    def _start(self, event):
        if self.message is not None:
            return self.message
        self.message = self.source_message.reply_with(
            {"type": "text", "text": "Thinking…"}
        )
        raw = dict(self.message.raw or {})
        raw["stream"] = self._stream_metadata("started", event)
        self.message.raw = raw
        self.message.save(update_fields=["raw"])
        self._last_flush = time.monotonic()
        return self.message

    def _delta(self, delta):
        if self.message is None:
            self._start({"type": "started"})
        self.text += delta
        now = time.monotonic()
        if now - self._last_flush >= self.flush_interval:
            self._save("streaming")
            self._last_flush = now
        return self.message

    def _save(self, status, event=None):
        raw = dict(self.message.raw or {})
        raw["stream"] = self._stream_metadata(status, event)
        self.message.text = self.text or "Thinking…"
        self.message.raw = raw
        self.message.save(update_fields=["text", "raw"])

    def _finish(self, event):
        if self.message is None:
            self._start({"type": "started"})
        if event.get("text") is not None:
            self.text = event["text"]
        self._save("finished", event)
        return self.message

    def _fail(self, event):
        if self.message is None:
            self._start({"type": "started"})
        if not self.text:
            self.text = "The response failed before any text was received."
        self._save("failed", event)
        return self.message
