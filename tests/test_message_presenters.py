from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from unicom.consumers.webchat_consumer import WebChatConsumer
from unicom.services.message_serialization import serialize_message
from unicom.services.webchat.presentation import serialize_webchat_message
from unicom.services.tool_presentations import extract_tool_presentation


def example_presenter(message, payload, *, viewer=None):
    return {**payload, "order_label": str(viewer.pk) if viewer else "guest"}


class MessagePresenterTests(SimpleTestCase):
    def setUp(self):
        self.message = SimpleNamespace(
            pk="message", text="hello", html="", media_type="text", raw={},
            media=None, is_outgoing=False, sender_name="Example",
            timestamp=timezone.now(), reply_to_message_id=None,
            channel=SimpleNamespace(pk=23),
        )

    def test_default_is_unchanged(self):
        self.assertEqual(serialize_message(self.message), serialize_message(self.message, presenter=None, viewer=object()))

    def test_explicit_custom_presentation_precedes_inferred_media(self):
        raw = {"tool_response": {"result": {
            "_unicom_presentation": {"type": "example.order", "label": "Ready"},
            "_responses_content": [{"type": "input_image", "image_url": "data:image/png;base64,AA=="}],
        }}}
        self.assertEqual(extract_tool_presentation(raw)["type"], "image")
        self.assertEqual(extract_tool_presentation(raw, custom_types={"example.order": lambda item: {"type": item["type"], "label": item["label"]}}), {"type": "example.order", "label": "Ready"})
        self.assertIsNone(extract_tool_presentation(raw, custom_types={"example.order": lambda item: None}))

    def test_unknown_custom_types_and_invalid_validator_outputs(self):
        raw = {"tool_response": {"result": {"_unicom_presentation": {"type": "example.order"}}}}
        self.assertIsNone(extract_tool_presentation(raw, custom_types={}))
        with self.assertRaises(ValueError):
            extract_tool_presentation(raw, custom_types={"example.order": lambda item: {"type": "other"}})

    def test_viewer_is_explicit_and_is_not_cached(self):
        first = serialize_message(self.message, presenter=example_presenter, viewer=SimpleNamespace(pk=1))
        second = serialize_message(self.message, presenter=example_presenter, viewer=SimpleNamespace(pk=2))
        self.assertEqual(first["order_label"], "1")
        self.assertEqual(second["order_label"], "2")
        self.assertNotIn("order_label", serialize_message(self.message))
        self.assertEqual(self.message.raw, {})

    def test_presenter_cannot_change_message_identity(self):
        with self.assertRaises(ValueError):
            serialize_message(self.message, presenter=lambda *args, **kwargs: {"id": "other"})

    @override_settings(UNICOM_WEBCHAT_MESSAGE_PRESENTERS={"23": example_presenter})
    def test_http_and_polling_use_the_same_presenter(self):
        viewer = SimpleNamespace(pk=1)
        consumer = WebChatConsumer()
        consumer.channel = self.message.channel
        consumer.scope = {"user": viewer}
        self.assertEqual(serialize_webchat_message(self.message, viewer=viewer), consumer._serialize_message(self.message))

    def test_live_updates_are_reloaded_per_recipient(self):
        consumer = WebChatConsumer()
        consumer.message_presenter = example_presenter
        consumer.chat_id = "chat"
        consumer.send_json = AsyncMock()
        consumer._present_updated_message = AsyncMock(return_value={"id": "message", "order_label": "1"})
        async_to_sync(consumer.webchat_message_updated)({"chat_id": "chat", "message": {"id": "message", "order_label": "untrusted"}})
        consumer._present_updated_message.assert_awaited_once_with("message")
        self.assertEqual(consumer.send_json.call_args.args[0]["message"]["order_label"], "1")

    def test_cross_chat_and_missing_updates_are_not_forwarded(self):
        consumer = WebChatConsumer()
        consumer.message_presenter = example_presenter
        consumer.chat_id = "chat"
        consumer.send_json = AsyncMock()
        consumer._present_updated_message = AsyncMock(return_value=None)
        async_to_sync(consumer.webchat_message_updated)({"chat_id": "other", "message": {"id": "message"}})
        consumer._present_updated_message.assert_not_awaited()
        async_to_sync(consumer.webchat_message_updated)({"chat_id": "chat", "message": {"id": "gone"}})
        consumer.send_json.assert_not_awaited()

    def test_reload_is_scoped_to_authorized_chat(self):
        consumer = WebChatConsumer()
        consumer.chat_id = "authorized"
        with patch("unicom.models.Message.objects.filter") as query:
            query.return_value.first.return_value = None
            self.assertIsNone(async_to_sync(consumer._present_updated_message)("foreign"))
            query.assert_called_once_with(pk="foreign", chat_id="authorized")
