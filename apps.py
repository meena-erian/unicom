from django.apps import AppConfig
from unicom.services.telegram.set_telegram_webhook import set_telegram_webhook
from pprint import pprint


class UnicomConfig(AppConfig):
    name = 'unicom'

    def ready(self):
        import unicom.signals
