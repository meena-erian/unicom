from django.urls import path
from unicom.views.telegram_webhook import telegram_webhook
from unicom.views.whatsapp_webhook import whatsapp_webhook

urlpatterns = [
    path('telegram/<int:bot_id>', telegram_webhook),
    path('whatsapp', whatsapp_webhook),
]
