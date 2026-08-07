import uuid
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from unicom.models import Account, Channel, Chat, Message, Request, ToolCall
from unicom.services.llm.tool_calls import save_tool_call


class ToolCallBatchTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(
            name="batch-tests", platform="WebChat", config={}
        )
        self.account = Account.objects.create(
            id="batch-user", channel=self.channel, platform="WebChat", raw={}
        )
        self.chat = Chat.objects.create(
            id="batch-chat", channel=self.channel, platform="WebChat"
        )
        self.message = self._user_message("Run both")
        self.request = Request.objects.create(
            message=self.message,
            account=self.account,
            channel=self.channel,
        )

    def _user_message(self, text):
        return Message.objects.create(
            id=f"message-{uuid.uuid4()}",
            channel=self.channel,
            platform="WebChat",
            sender=self.account,
            chat=self.chat,
            is_outgoing=False,
            sender_name="User",
            text=text,
            timestamp=timezone.now(),
            raw={},
        )

    def _tool_call(self, suffix, *, status="ACTIVE"):
        call_id = f"call-{suffix}"
        call_message = save_tool_call(
            self.chat, "test_tool", {}, call_id=call_id,
            reply_to_message=self.message,
        )
        return ToolCall.objects.create(
            call_id=call_id,
            tool_name="test_tool",
            arguments={},
            status=status,
            request=self.request,
            tool_call_message=call_message,
            initial_user_message=self.message,
        )

    @patch.object(Request, "categorize")
    @patch.object(Request, "identify_member")
    def test_parallel_batch_continues_once_after_all_calls_respond(
        self, _identify_member, _categorize
    ):
        first = self._tool_call("first")
        second = self._tool_call("second")

        _message, continuation = first.respond({"result": "first"})
        self.assertIsNone(continuation)

        _message, continuation = second.respond({"result": "second"})
        self.assertIsNotNone(continuation)
        self.assertEqual(self.request.child_requests.count(), 1)
        context = continuation.message.as_llm_chat(mode="thread", multimodal=False)
        self.assertEqual(
            [item["role"] for item in context],
            ["user", "assistant", "tool", "assistant", "tool"],
        )
        self.assertEqual(
            [
                item["tool_calls"][0]["id"]
                for item in context if item.get("tool_calls")
            ],
            [first.call_id, second.call_id],
        )
        tool_contents = [item["content"] for item in context if item["role"] == "tool"]
        self.assertIn("first", tool_contents[0])
        self.assertIn("second", tool_contents[1])

    def test_newer_user_message_suppresses_late_tool_response(self):
        tool_call = self._tool_call("late")
        self._user_message("Stop")

        response_message, continuation = tool_call.respond({"result": "late"})

        self.assertIsNone(response_message)
        self.assertIsNone(continuation)
        tool_call.refresh_from_db()
        self.assertEqual(tool_call.status, "INTERRUPTED")
        self.assertEqual(self.request.child_requests.count(), 0)

    @patch.object(Request, "categorize")
    @patch.object(Request, "identify_member")
    def test_later_active_responses_remain_recurring_continuations(
        self, _identify_member, _categorize
    ):
        tool_call = self._tool_call("recurring")

        tool_call.respond({"day": 1})
        tool_call.respond({"day": 2})

        self.assertEqual(self.request.child_requests.count(), 2)
