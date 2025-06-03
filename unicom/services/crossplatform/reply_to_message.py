from __future__ import annotations
from typing import TYPE_CHECKING
from unicom.services.telegram.send_telegram_message import send_telegram_message
from unicom.services.whatsapp.send_whatsapp_message import send_whatsapp_message
from unicom.services.internal.send_internal_message import send_internal_message
from unicom.services.email.send_email_message import send_email_message
from unicom.services.decode_base64_image import decode_base64_image
from unicom.models import Message, Channel
import uuid
import os

if TYPE_CHECKING:
    from unicom.models import Message, Channel


def speak_text(text, audio_file):
    pass # TODO: Remove or add implementation for speak text


def reply_to_message(channel:Channel , message: Message, response: dict) -> Message:
    """
    response can contain:
      - "type": 'text', 'audio', or 'image'
      - "text":   The text or caption
      - "html":   The HTML body for email messages
      - "file_path" or "base64_image" or "image_link" 
    """

    # If it's an image in base64, decode it:
    if response.get("type") == "image" and "base64_image" in response:
        # decode_base64_image => returns "media/<uuid>.jpg"
        relative_path = decode_base64_image(response["base64_image"], output_subdir="media")
        response["file_path"] = relative_path
        response.pop("base64_image")  # Remove it so we don't pass raw base64 around

    # Example logic if original message was audio
    if message.media_type == 'audio':
        response['type'] = "audio"
        audio_file_name = os.path.join("media", f"{uuid.uuid4()}.oga")  # store in media/
        speak_text(response['text'], audio_file_name)
        response['file_path'] = audio_file_name
        response['text'] = f"**Voice Message**\n{response['text']}"

    # Dispatch by platform
    platform = message.platform
    if platform == 'Telegram':
        return send_telegram_message(channel, {
            "chat_id": message.chat_id,
            "reply_to_message_id": message.id,
            "parse_mode": "Markdown",
            **response
        })
    elif platform == 'WhatsApp':
        return send_whatsapp_message({
            "chat_id": message.chat_id,
            "reply_to_message_id": message.id,
            **response
        })
    elif platform == 'Internal':
        source_function_call = message.triggered_function_calls.first()
        return send_internal_message({
            "reply_to_message_id": message.id,
            **response
        }, source_function_call=source_function_call)
    elif platform == 'Email':
        return send_email_message(channel, {
            'reply_to_message_id' : message.id,
            'text'                : response.get('text', None),
            'html'                : response.get('html', None),
            'cc'                  : getattr(message, 'cc', []),
            'bcc'                 : getattr(message, 'bcc', []),
            'attachments'         : ([response['file_path']]
                                     if response.get('file_path') else []),
        })
    else:
        print(f"Unsupported platform: {platform}")
        return None
