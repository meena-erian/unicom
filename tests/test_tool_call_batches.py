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
            raw={"skip_request_creation": True},
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

    def _preamble(self, parent, text="I will run the requested checks."):
        return Message.objects.create(
            id=f"preamble-{uuid.uuid4()}",
            channel=self.channel,
            platform="WebChat",
            sender=self.account,
            chat=self.chat,
            is_outgoing=True,
            sender_name="Assistant",
            text=text,
            reply_to_message=parent,
            timestamp=timezone.now(),
            raw={"assistant_phase": "tool_preamble"},
            media_type="text",
        )

    def _link(self, call, preamble):
        call.tool_call_message.raw["assistant_preamble_message_id"] = str(preamble.pk)
        call.tool_call_message.save(update_fields=["raw"])

    def _assert_pairs(self, context):
        for index, item in enumerate(context):
            if item.get('tool_calls'):
                self.assertEqual(context[index + 1]['role'], 'tool')
                self.assertEqual(context[index + 1]['tool_call_id'], item['tool_calls'][0]['id'])

    def test_replay_before_output_excludes_future_preamble(self):
        preamble = self._preamble(self.message)
        call = self._tool_call('future', status='PENDING')
        self._link(call, preamble)
        call.interrupt()
        self.assertEqual(self.message.as_llm_chat(mode='thread', multimodal=False), [
            {'role': 'user', 'content': self.message.text},
        ])

    @patch.object(Request, 'categorize')
    @patch.object(Request, 'identify_member')
    def test_branch_from_preamble_excludes_subsequent_execution(self, _identify, _categorize):
        first = self._tool_call('before-branch', status='PENDING')
        _response, continuation = first.respond({'result': 'first'})
        preamble = self._preamble(continuation.message, 'Second stage')
        second = continuation.submit_tool_calls([
            {'id': 'call-after-branch', 'name': 'test_tool', 'arguments': {}},
        ])[0]
        self._link(second, preamble)
        second.respond({'result': 'second'})
        branch = self._user_message('Branch at second stage')
        branch.reply_to_message = preamble
        branch.save(update_fields=['reply_to_message'])
        Request.objects.create(message=branch, account=self.account, channel=self.channel)

        context = branch.as_llm_chat(mode='thread', multimodal=False)
        self.assertEqual([item['tool_calls'][0]['id'] for item in context if item.get('tool_calls')], [first.call_id])
        self.assertEqual(context[-2:], [
            {'role': 'assistant', 'content': preamble.text},
            {'role': 'user', 'content': branch.text},
        ])
        self._assert_pairs(context)

    @patch.object(Request, 'categorize')
    @patch.object(Request, 'identify_member')
    def test_reverse_completion_keeps_entire_batch_before_child(self, _identify, _categorize):
        preamble = self._preamble(self.message)
        first = self._tool_call('reverse-first', status='PENDING')
        second = self._tool_call('reverse-second', status='PENDING')
        self._link(first, preamble)
        self._link(second, preamble)
        second.respond({'result': 'second finishes first'})
        _response, continuation = first.respond({'result': 'first finishes last'})
        child_preamble = self._preamble(continuation.message, 'Now the next stage')
        child_call = continuation.submit_tool_calls([
            {'id': 'call-next-stage', 'name': 'test_tool', 'arguments': {}},
        ])[0]
        self._link(child_call, child_preamble)
        response, _continuation = child_call.respond({'result': 'child'})
        context = response.as_llm_chat(mode='thread', multimodal=False)
        self.assertEqual([item['tool_calls'][0]['id'] for item in context if item.get('tool_calls')], [
            first.call_id, second.call_id, child_call.call_id,
        ])
        self.assertEqual(context[6]['content'], child_preamble.text)
        self.assertNotIn(child_preamble.text, [item.get('content') for item in continuation.message.as_llm_chat(mode='thread')])
        self._assert_pairs(context)

    @patch.object(Request, 'categorize')
    @patch.object(Request, 'identify_member')
    def test_recurring_responses_include_linked_text_once(self, _identify, _categorize):
        preamble = self._preamble(self.message)
        call = self._tool_call('linked-recurring')
        self._link(call, preamble)
        call.respond({'event': 1})
        response, _continuation = call.respond({'event': 2})
        context = response.as_llm_chat(mode='thread', multimodal=False)
        self.assertEqual(sum(item.get('content') == preamble.text for item in context), 1)
        self.assertEqual(sum(item.get('role') == 'tool' for item in context), 2)
        self._assert_pairs(context)

    def test_invalid_link_is_ignored(self):
        other_parent = self._preamble(self.message, 'Different parent')
        wrong_preamble = self._preamble(other_parent, 'Do not include')
        call = self._tool_call('invalid-link', status='PENDING')
        self._link(call, wrong_preamble)
        response = call.interrupt()
        context = response.as_llm_chat(mode='thread', multimodal=False)
        self.assertNotIn(wrong_preamble.text, [item.get('content') for item in context])
        self._assert_pairs(context)

    @patch.object(Request, 'categorize')
    @patch.object(Request, 'identify_member')
    def test_branch_from_earlier_final_answer_excludes_later_active_events(self, _identify, _categorize):
        preamble = self._preamble(self.message)
        call = self._tool_call('active-branch')
        self._link(call, preamble)
        _response, continuation = call.respond({'event': 'selected'})
        final = continuation.message.reply_with({'type': 'text', 'text': 'First result'})
        call.respond({'event': 'later event not selected'})
        branch = self._user_message('Reply to first result')
        branch.reply_to_message = final
        branch.save(update_fields=['reply_to_message'])
        Request.objects.create(message=branch, account=self.account, channel=self.channel)
        context = branch.as_llm_chat(mode='thread', multimodal=False)
        self.assertEqual(sum(item.get('role') == 'tool' for item in context), 1)
        self.assertNotIn('later event not selected', str(context))
        self.assertEqual(sum(item.get('content') == preamble.text for item in context), 1)
        self._assert_pairs(context)

    def test_foreign_chat_link_is_ignored(self):
        preamble = self._preamble(self.message)
        other_chat = Chat.objects.create(id='foreign-chat', channel=self.channel, platform='WebChat')
        Message.objects.filter(pk=preamble.pk).update(chat=other_chat)
        call = self._tool_call('foreign-link', status='PENDING')
        self._link(call, preamble)
        response = call.interrupt()
        context = response.as_llm_chat(mode='thread', multimodal=False)
        self.assertNotIn(preamble.text, [item.get('content') for item in context])
        self._assert_pairs(context)

    def test_preamble_is_projected_once_before_parallel_tool_pairs(self):
        preamble = self._preamble(self.message)
        calls = self.request.submit_tool_calls([
            {"id": "call-preamble-first", "name": "test_tool", "arguments": {}},
            {"id": "call-preamble-second", "name": "test_tool", "arguments": {}},
        ])
        for call in calls:
            call.tool_call_message.raw["assistant_preamble_message_id"] = str(preamble.pk)
            call.tool_call_message.save(update_fields=["raw"])
        calls[0].respond({"result": "first"})
        _response, continuation = calls[1].respond({"result": "second"})

        context = continuation.message.as_llm_chat(mode="thread", multimodal=False)
        self.assertEqual(
            [item["role"] for item in context],
            ["user", "assistant", "assistant", "tool", "assistant", "tool"],
        )
        self.assertEqual(context[1]["content"], preamble.text)
        self.assertEqual(
            [item["tool_calls"][0]["id"] for item in context if item.get("tool_calls")],
            ["call-preamble-first", "call-preamble-second"],
        )

    def test_unlinked_legacy_preamble_is_not_inferred_from_sibling_position(self):
        preamble = self._preamble(self.message)
        calls = self.request.submit_tool_calls([
            {"id": "call-legacy-preamble", "name": "test_tool", "arguments": {}},
        ])
        calls[0].respond({"result": "done"})

        context = calls[0].response_messages.first().as_llm_chat(
            mode="thread", multimodal=False,
        )
        self.assertNotIn(preamble.text, [item.get("content") for item in context])

    def test_preamble_projection_stays_with_selected_branch(self):
        branch_a = self._user_message("Branch A")
        branch_a.reply_to_message = self.message
        branch_a.save(update_fields=["reply_to_message"])
        request_a = Request.objects.create(
            message=branch_a, account=self.account, channel=self.channel,
        )
        preamble_a = self._preamble(branch_a, "Branch A work.")
        call_a = request_a.submit_tool_calls([
            {"id": "call-preamble-a", "name": "test_tool", "arguments": {}},
        ])[0]
        call_a.tool_call_message.raw["assistant_preamble_message_id"] = str(preamble_a.pk)
        call_a.tool_call_message.save(update_fields=["raw"])
        response_a = call_a.interrupt()

        branch_b = self._user_message("Branch B")
        branch_b.reply_to_message = self.message
        branch_b.save(update_fields=["reply_to_message"])
        request_b = Request.objects.create(
            message=branch_b, account=self.account, channel=self.channel,
        )
        preamble_b = self._preamble(branch_b, "Branch B work.")
        call_b = request_b.submit_tool_calls([
            {"id": "call-preamble-b", "name": "test_tool", "arguments": {}},
        ])[0]
        call_b.tool_call_message.raw["assistant_preamble_message_id"] = str(preamble_b.pk)
        call_b.tool_call_message.save(update_fields=["raw"])
        call_b.interrupt()

        context = response_a.as_llm_chat(mode="thread", multimodal=False)
        text = [item.get("content") for item in context if item.get("role") == "assistant"]
        self.assertIn("Branch A work.", text)
        self.assertNotIn("Branch B work.", text)

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
        self.assertEqual(tool_call.response_messages.count(), 1)
        self.assertEqual(tool_call.response_messages.get().raw["tool_response"]["result"]["status"], "ERROR")
        self.assertEqual(self.request.child_requests.count(), 0)

    @patch.object(Request, "categorize")
    @patch.object(Request, "identify_member")
    def test_large_results_are_fresh_for_batch_and_retry_but_not_next_cycle(self, *_mocks):
        first, second = self._tool_call("large-first"), self._tool_call("large-second")
        first.respond({"result": "first-marker" + "x" * 40000})
        response, continuation = second.respond({"result": "second-marker" + "y" * 40000})
        for mode in ("thread", "chat"):
            for _ in range(2):
                outputs = [m["content"] for m in response.as_llm_chat(mode=mode) if m["role"] == "tool"]
                self.assertEqual(len(outputs), 2)
                self.assertTrue(all(len(value) > 40000 for value in outputs))
        next_call = continuation.submit_tool_calls([
            {"id": "call-next", "name": "test_tool", "arguments": {}},
        ])[0]
        next_response, _ = next_call.respond({"result": "next-marker" + "z" * 40000})
        outputs = [m["content"] for m in next_response.as_llm_chat(mode="thread") if m["role"] == "tool"]
        self.assertEqual(len(outputs), 3)
        self.assertTrue(all("OMITTED_FROM_HISTORY" in value for value in outputs[:2]))
        self.assertIn("next-marker", outputs[2])
        later = self._user_message("Explain")
        later.reply_to_message = next_response
        later.save(update_fields=["reply_to_message"])
        outputs = [m["content"] for m in later.as_llm_chat(mode="thread") if m["role"] == "tool"]
        self.assertTrue(outputs)
        self.assertTrue(all("OMITTED_FROM_HISTORY" in value for value in outputs))

    @patch.object(Request, "categorize")
    @patch.object(Request, "identify_member")
    def test_later_user_turn_retains_every_parallel_sibling(
        self, _identify_member, _categorize
    ):
        first = self._tool_call("first")
        second = self._tool_call("second")
        first.respond({"device": "alpine"})
        _response, continuation = second.respond({"device": "ubuntu"})
        assistant = continuation.message.reply_with({"type": "text", "text": "Both done"})
        later_user = self._user_message("What happened?")
        later_user.reply_to_message = assistant
        later_user.save(update_fields=["reply_to_message"])
        Request.objects.create(
            message=later_user, account=self.account, channel=self.channel,
        )

        context = later_user.as_llm_chat(mode="thread", multimodal=False)

        call_ids = [
            item["tool_calls"][0]["id"] for item in context
            if item.get("tool_calls")
        ]
        self.assertEqual(call_ids, [first.call_id, second.call_id])
        self.assertEqual(
            [item["tool_call_id"] for item in context if item["role"] == "tool"],
            call_ids,
        )

    def test_interrupted_historical_call_gets_synthetic_projection(self):
        tool_call = self._tool_call("historical", status="PENDING")
        ToolCall.objects.filter(pk=tool_call.pk).update(status="INTERRUPTED")
        interrupt = self._user_message("Stop now")
        interrupt.reply_to_message = self.message
        interrupt.save(update_fields=["reply_to_message"])
        Request.objects.create(
            message=interrupt, account=self.account, channel=self.channel,
        )

        context = interrupt.as_llm_chat(mode="thread", multimodal=False)

        self.assertEqual(context[-3]["tool_calls"][0]["id"], tool_call.call_id)
        self.assertEqual(context[-2]["role"], "tool")
        self.assertEqual(context[-2]["tool_call_id"], tool_call.call_id)
        self.assertIn("Interrupted", context[-2]["content"])
        self.assertEqual(context[-1]["content"], "Stop now")

    def test_stale_llm_output_cannot_submit_calls_after_new_user_turn(self):
        self._user_message("Newer input")

        calls = self.request.submit_tool_calls([{
            "id": "call-stale", "name": "test_tool", "arguments": {},
        }])

        self.assertEqual(calls, [])
        self.assertFalse(ToolCall.objects.filter(call_id="call-stale").exists())

    def test_projection_does_not_merge_edited_user_sibling_branch(self):
        common = self.message
        branch_a = self._user_message("Branch A")
        branch_a.reply_to_message = common
        branch_a.save(update_fields=["reply_to_message"])
        request_a = Request.objects.create(
            message=branch_a, account=self.account, channel=self.channel,
        )
        branch_b = self._user_message("Branch B")
        branch_b.reply_to_message = common
        branch_b.save(update_fields=["reply_to_message"])
        request_b = Request.objects.create(
            message=branch_b, account=self.account, channel=self.channel,
        )
        endpoints = {}
        for request, message, suffix in (
            (request_a, branch_a, "branch-a"),
            (request_b, branch_b, "branch-b"),
        ):
            call_message = save_tool_call(
                self.chat, "test_tool", {}, call_id=f"call-{suffix}",
                reply_to_message=message,
            )
            call = ToolCall.objects.create(
                call_id=f"call-{suffix}", tool_name="test_tool", arguments={},
                status="PENDING", request=request,
                tool_call_message=call_message, initial_user_message=message,
            )
            endpoints[suffix] = call.interrupt()

        context = endpoints["branch-a"].as_llm_chat(mode="thread", multimodal=False)
        call_ids = [
            item["tool_calls"][0]["id"] for item in context
            if item.get("tool_calls")
        ]
        self.assertIn("call-branch-a", call_ids)
        self.assertNotIn("call-branch-b", call_ids)

    @patch.object(Request, "categorize")
    @patch.object(Request, "identify_member")
    def test_later_active_responses_remain_recurring_continuations(
        self, _identify_member, _categorize
    ):
        tool_call = self._tool_call("recurring")

        tool_call.respond({"day": 1})
        tool_call.respond({"day": 2})

        self.assertEqual(self.request.child_requests.count(), 2)
