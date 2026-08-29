from unittest.mock import Mock

from django.test import SimpleTestCase

from unicom.services.webchat.streaming import WebChatMessageStreamSink


class WebChatMessageStreamSinkTests(SimpleTestCase):
    def setUp(self):
        self.pending = Mock()
        self.pending.raw = {"source": "webchat_outgoing"}
        self.source = Mock(platform="WebChat")
        self.source.reply_with.return_value = self.pending
        self.sink = WebChatMessageStreamSink(self.source, flush_interval=0)

    def test_projects_deltas_into_one_message_and_finishes(self):
        self.assertIs(self.sink({"type": "started"}), self.pending)
        self.sink({"type": "text.delta", "delta": "Hel"})
        self.sink({"type": "text.delta", "delta": "lo"})
        result = self.sink({
            "type": "finished", "text": "Hello", "response_id": "resp_123",
        })

        self.assertIs(result, self.pending)
        self.source.reply_with.assert_called_once_with({"type": "text", "text": "Thinking…"})
        self.assertEqual(self.pending.text, "Hello")
        self.assertEqual(self.pending.raw["stream"]["status"], "finished")
        self.assertEqual(self.pending.raw["stream"]["response_id"], "resp_123")

    def test_failure_leaves_a_durable_retryable_message(self):
        self.sink({"type": "started"})
        self.sink({"type": "failed", "error": "gateway unavailable"})

        self.assertIn("failed before any text", self.pending.text)
        self.assertEqual(self.pending.raw["stream"]["status"], "failed")
        self.assertEqual(self.pending.raw["stream"]["error"], "gateway unavailable")

    def test_rejects_non_webchat_messages(self):
        with self.assertRaisesRegex(ValueError, "WebChat"):
            WebChatMessageStreamSink(Mock(platform="Email"))
