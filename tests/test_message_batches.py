import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from unicom.models import Account, AccountChat, Channel, Chat, Message, Request
from unicom.services.message_batches import save_incoming_message_batch
from unicom.services.webchat.save_webchat_message import save_webchat_messages
from unicom.views.webchat_views import send_webchat_message_api


class MessageBatchTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.storage = override_settings(MEDIA_ROOT=self.directory.name)
        self.storage.enable()
        self.addCleanup(self.storage.disable)
        self.channel = Channel.objects.create(name="Example", platform="WebChat", config={})
        Channel.objects.filter(pk=self.channel.pk).update(active=True)
        self.account = Account.objects.create(id="example-account", name="Example", channel=self.channel, platform="WebChat")
        self.chat = Chat.objects.create(id="example-chat", channel=self.channel, platform="WebChat")
        AccountChat.objects.create(account=self.account, chat=self.chat)

    def part(self, identifier):
        return Message(
            id=identifier, channel=self.channel, platform="WebChat",
            sender=self.account, chat=self.chat, is_outgoing=False,
            sender_name="Example", text=identifier, timestamp=timezone.now(), raw={},
        )

    def test_ordered_group_preserves_single_message_history_and_queues_nothing(self):
        first, second = save_incoming_message_batch([self.part("first"), self.part("second")])
        self.assertEqual(second.reply_to_message_id, first.pk)
        self.assertEqual(Request.objects.count(), 0)
        history = second.as_llm_chat(mode="thread", multimodal=False)
        self.assertEqual([item["content"] for item in history], ["first", "second"])

    def test_cross_chat_batch_is_rejected_before_any_writes(self):
        first, second = self.part("first"), self.part("second")
        second.chat = Chat.objects.create(id="other", channel=self.channel, platform="WebChat")
        with self.assertRaises(ValueError):
            save_incoming_message_batch([first, second])
        self.assertEqual(Message.objects.count(), 0)

    def test_batch_failure_rolls_back_all_messages(self):
        first, second = self.part("first"), self.part("second")
        with patch.object(second, "save", side_effect=RuntimeError("storage failure")):
            with self.assertRaises(RuntimeError):
                save_incoming_message_batch([first, second])
        self.assertEqual(Message.objects.count(), 0)

    def test_duplicate_ids_and_outgoing_messages_are_rejected(self):
        with self.assertRaises(ValueError):
            save_incoming_message_batch([self.part("same"), self.part("same")])
        outgoing = self.part("outgoing")
        outgoing.is_outgoing = True
        with self.assertRaises(ValueError):
            save_incoming_message_batch([outgoing])

    def request(self, files):
        request = RequestFactory().post("/send/", {"text": "Compare", "chat_id": self.chat.pk, "channel_id": self.channel.pk, "files": files})
        request.user = AnonymousUser()
        request.session = {}
        return request

    def files(self):
        return [SimpleUploadedFile("one.png", b"first", content_type="image/png"), SimpleUploadedFile("two.wav", b"second", content_type="audio/wav")]

    def test_http_multiple_attachments_create_one_request_for_the_complete_turn(self):
        import json

        with patch("unicom.services.webchat.save_webchat_message.get_or_create_account", return_value=self.account):
            response = send_webchat_message_api(self.request(self.files()))
        self.assertEqual(response.status_code, 200, response.content)
        payload = json.loads(response.content)
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["message"]["id"], payload["messages"][-1]["id"])
        self.assertEqual(Request.objects.count(), 1)
        queued = Request.objects.get()
        self.assertEqual(queued.message_id, payload["message"]["id"])
        self.assertEqual(queued.message.reply_to_message_id, payload["messages"][0]["id"])
        self.assertEqual(queued.display_text, "Compare")

    def test_unauthorized_chat_and_invalid_file_fail_without_messages(self):
        AccountChat.objects.all().delete()
        with patch("unicom.services.webchat.save_webchat_message.get_or_create_account", return_value=self.account):
            response = send_webchat_message_api(self.request(self.files()))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Message.objects.count(), 0)
        files = [SimpleUploadedFile("bad.exe", b"bad", content_type="application/octet-stream")]
        self.assertEqual(send_webchat_message_api(self.request(files)).status_code, 400)

    def test_handoff_batch_does_not_create_requests(self):
        with patch("unicom.services.webchat.save_webchat_message.get_or_create_account", return_value=self.account), patch("unicom.services.webchat.save_webchat_message.chat_allows_automation", return_value=False):
            response = send_webchat_message_api(self.request(self.files()))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(Request.objects.count(), 0)

    def test_failure_removes_uploaded_files_and_rolls_back_request(self):
        from pathlib import Path

        with patch("unicom.services.webchat.save_webchat_message.get_or_create_account", return_value=self.account), patch("unicom.models.Request.objects.get_or_create", side_effect=RuntimeError("queue failed")):
            response = send_webchat_message_api(self.request(self.files()))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(Request.objects.count(), 0)
        self.assertEqual([path for path in Path(self.directory.name).rglob("*") if path.is_file()], [])

    def test_uploading_media_does_not_persist_an_incomplete_message(self):
        first = self.part("existing")
        first.media.save("one.png", self.files()[0], save=False)
        save_incoming_message_batch([first])
        second = self.part("new")
        second.media.save("one.png", self.files()[0], save=False)
        self.assertTrue(second._state.adding)
        self.assertFalse(Message.objects.filter(pk=second.pk).exists())
        self.assertTrue(second.media.name)

    def test_other_channel_is_not_treated_as_a_webchat_album(self):
        channel = SimpleNamespace(platform="Telegram")
        with self.assertRaises(ValueError):
            save_webchat_messages(channel, {"files": self.files()}, self.request([]))
