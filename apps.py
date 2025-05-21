from django.apps import AppConfig
from unicom.services.telegram.set_telegram_webhook import set_telegram_webhook
from bot_template.credentials import DJANGO_PUBLIC_PROTOCOL, DJANGO_PUBLIC_HOST, DJANGO_PUBLIC_PORT
from pprint import pprint


class UnicomConfig(AppConfig):
    name = 'unicom'

    def ready(self):
        import unicom.signals
