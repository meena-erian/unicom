from types import SimpleNamespace

from django.test import SimpleTestCase

from unicom.services.webchat.attachments import validate_webchat_attachments


class AttachmentPolicyTests(SimpleTestCase):
    def upload(self, size=1, content_type="image/png"):
        return SimpleNamespace(size=size, content_type=content_type)

    def test_policy_is_webchat_specific_and_configurable(self):
        channel = SimpleNamespace(platform="WebChat", config={"webchat_uploads": {"max_files": 2, "max_file_bytes": 4, "max_total_bytes": 5}})
        validate_webchat_attachments(channel, [self.upload(2), self.upload(3)])
        with self.assertRaises(ValueError):
            validate_webchat_attachments(channel, [self.upload(3), self.upload(3)])
        with self.assertRaises(ValueError):
            validate_webchat_attachments(SimpleNamespace(platform="Telegram", config={}), [self.upload()])

    def test_disallowed_types_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_webchat_attachments(SimpleNamespace(platform="WebChat", config={}), [self.upload(content_type="application/zip")])
