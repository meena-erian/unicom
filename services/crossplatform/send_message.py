from unicom.services.telegram.send_telegram_message import send_telegram_message
from unicom.services.whatsapp.send_whatsapp_message import send_whatsapp_message
from unicom.services.email.send_email_message import send_email_message
from django.contrib.auth.models import User
from django.apps import apps


def send_message(msg:dict, user:User=None):
    """
    The msg dict must include at least the chat_id, and text
    """
    Chat = apps.get_model('unicom', 'Chat')
    if not msg.get('platform'):
        chat = Chat.objects.get(id=msg['chat_id'])
        msg['platform'] = chat.platform
    platform = msg.pop('platform')
    if platform == 'Telegram':
        params = {
            "parse_mode": "Markdown",
            **msg
        }
        return send_telegram_message(params, user)
    elif platform == 'WhatsApp':
        return send_whatsapp_message(msg, user)
    elif platform == 'Email':
        return send_email_message(msg, user)