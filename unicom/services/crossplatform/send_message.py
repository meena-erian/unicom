from __future__ import annotations
from typing import TYPE_CHECKING
from unicom.services.telegram.send_telegram_message import send_telegram_message
from unicom.services.whatsapp.send_whatsapp_message import send_whatsapp_message
from unicom.services.email.send_email_message import send_email_message
from django.contrib.auth.models import User

if TYPE_CHECKING:
    from unicom.models import Channel


def send_message(channel: Channel, msg:dict, user:User=None):
    """
    The msg dict must include at least the chat_id, and text
    """
    if channel.platform == 'Telegram':
        return send_telegram_message(channel, msg, user)
    elif channel.platform == 'WhatsApp':
        return send_whatsapp_message(channel, msg, user)
    elif channel.platform == 'Email':
        return send_email_message(channel, msg, user)