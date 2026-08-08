from django.test import SimpleTestCase

from unicom.services.tool_presentations import extract_tool_presentation


class ToolPresentationTests(SimpleTestCase):
    def test_explicit_image_presentation_is_extracted(self):
        raw = {"tool_response": {"result": {"status": "SUCCESS", "result": '{"result":"Image inspected","_unicom_presentation":{"type":"image","url":"data:image/png;base64,AAAA","alt":"Preview","caption":"/photo.png"}}'}}}
        self.assertEqual(extract_tool_presentation(raw), {
            "type": "image", "url": "data:image/png;base64,AAAA",
            "alt": "Preview", "caption": "/photo.png",
        })

    def test_responses_image_block_supports_historical_results(self):
        raw = {"tool_response": {"result": {"result": '{"path":"/old.png","_responses_content":[{"type":"input_image","image_url":"data:image/png;base64,OLD"}]}'}}}
        self.assertEqual(extract_tool_presentation(raw), {
            "type": "image", "url": "data:image/png;base64,OLD",
            "alt": "Tool image", "caption": "/old.png",
        })

    def test_unsafe_image_url_is_rejected(self):
        raw = {"tool_response": {"result": {"_unicom_presentation": {"type": "image", "url": "javascript:alert(1)"}}}}
        self.assertIsNone(extract_tool_presentation(raw))

    def test_inline_svg_is_rejected(self):
        raw = {"tool_response": {"result": {"_unicom_presentation": {"type": "image", "url": "data:image/svg+xml,<svg onload=alert(1)>"}}}}
        self.assertIsNone(extract_tool_presentation(raw))
