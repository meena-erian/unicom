# robopower.services.telegram.send_telegram_message.py
from __future__ import annotations
from typing import TYPE_CHECKING
from unicom.services.telegram.save_telegram_message import save_telegram_message
from unicom.services.telegram.escape_markdown import escape_markdown
from django.contrib.auth.models import User
from django.conf import settings
import requests
import time
import os

if TYPE_CHECKING:
    from unicom.models import Channel


def send_telegram_message(channel: Channel, params: dict, user: User=None, retry_interval=60, max_retries=7):
    """
    Params must include at least chat_id and text (if sending a text message or caption).
    If 'type' == 'audio', we send an audio file.
    If 'type' == 'image', we send a photo, with optional caption in 'text'.
    """
    if not "parse_mode" in params:
        params["parse_mode"] = "Markdown"
    TelegramCredentials = channel.config
    TELEGRAM_API_TOKEN = TelegramCredentials["TELEGRAM_API_TOKEN"]
    if TELEGRAM_API_TOKEN is None:
        raise Exception("send_telegram_message failed as no TELEGRAM_API_TOKEN was defined")

    files = None
    url = None

    if 'type' in params:
        msg_type = params['type']
        # Sending audio
        if msg_type == 'audio':
            url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendAudio"
            files = {"audio": open(params['file_path'], 'rb')}
            params.pop('file_path', None)
            params.pop('type', None)

        # Sending image
        elif msg_type == 'image':
            url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendPhoto"
            # Expecting a local file_path to open, or adapt if you have a direct URL
            absolute_path = params['file_path']
            if not os.path.isabs(absolute_path):
                absolute_path = os.path.join(settings.MEDIA_ROOT, absolute_path)
            if 'file_path' in params:
                files = {"photo": open(absolute_path, 'rb')}
                params.pop('file_path', None)
            # If there's textual caption
            if 'text' in params:
                params['caption'] = params['text']
                params.pop('text', None)
            params.pop('type', None)
            params.pop('image_base64', None)

        # Otherwise fallback to a basic text message
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"

    else:
        # If 'type' not present, treat it like a standard text message
        url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"
        msg_type = 'text'

    retries = 0
    while retries <= max_retries:
        print(f"Attempt {retries} to send telegram message")
        response = requests.post(url, data=params, files=files)
        ret = response.json()

        if ret.get('ok'):
            return save_telegram_message(channel, ret.get('result'), user)
        elif 'error_code' in ret and ret['error_code'] == 429:  # Rate limit
            time.sleep(retry_interval)
            retries += 1
        elif 'error_code' in ret and ret['error_code'] == 400 and params.get("parse_mode") == "Markdown":
            text_field_key = "caption" if msg_type == "image" else "text"
            # Common "can't parse" error, so try escaping or cropping
            print("Send telegram message failed with status 400 while parse_mode is Markdown", ret)
            if 'message is too long' in ret.get('description', ''):
                print(f"Message length: {len(params[text_field_key])}")
                cropping_footer = "\n\n… Message Cropped"
                params[text_field_key] = params[text_field_key][:4095 - len(cropping_footer)] + cropping_footer
            elif "Can't find end of the entity starting at byte offset" in ret.get('description', ''):
                # Extract mentioned byte offset from error message
                byte_offset = int(ret['description'].split("byte offset")[1].split()[0])
                print(f"Byte offset: {byte_offset}")
                mentioned_char = params[text_field_key][byte_offset]
                print(f"Mentioned char that's causing the error: \"{mentioned_char}\"")
                if text_field_key in params:
                    params[text_field_key] = escape_markdown(params[text_field_key])
            elif "file must be non-empty" in ret.get('description', ''):
                # Handle empty file case
                print("Empty file error, files: ", files)
            else:
                if text_field_key in params:
                    params[text_field_key] = escape_markdown(params[text_field_key])
            retries += 1
        else:
            print(params)
            print(ret)
            raise Exception("Failed to send telegram message")

    raise Exception("Failed to send telegram message after maximum retries")
