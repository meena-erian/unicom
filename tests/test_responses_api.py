from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from unicom.models.message import Message


class MessageResponsesApiTests(SimpleTestCase):
    def setUp(self):
        self.message = Mock(spec=Message)
        self.message.as_llm_chat.return_value = [{"role": "user", "content": "Hello"}]
        self.message.media_type = "text"
        self.message.platform = "WebChat"
        self.message.reply_with.return_value = "saved-reply"

    @patch("unicom.models.message.get_openai_client")
    def test_responses_mode_is_explicit_and_persists_output(self, get_client):
        get_client.return_value.responses.create.return_value = SimpleNamespace(output_text="Hi")

        result = Message.reply_using_llm(
            self.message, model="test-model", api_mode="responses"
        )

        self.assertEqual(result, "saved-reply")
        get_client.return_value.responses.create.assert_called_once_with(
            model="test-model",
            input=[{"role": "user", "content": "Hello"}],
        )
        get_client.return_value.chat.completions.create.assert_not_called()
        self.message.reply_with.assert_called_once_with({"type": "text", "text": "Hi"})

    @patch("unicom.models.message.get_openai_client")
    def test_default_mode_remains_chat_completions(self, get_client):
        get_client.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Hi", audio=None))]
        )

        Message.reply_using_llm(self.message, model="test-model")

        get_client.return_value.chat.completions.create.assert_called_once()
        get_client.return_value.responses.create.assert_not_called()

    def test_unknown_api_mode_is_rejected_before_provider_call(self):
        with self.assertRaisesRegex(ValueError, "api_mode"):
            Message.reply_using_llm(self.message, model="test-model", api_mode="unknown")
