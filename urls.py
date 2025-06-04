from django.urls import path
from unicom.views.telegram_webhook import telegram_webhook
from unicom.views.whatsapp_webhook import whatsapp_webhook
from unicom.views.email_tracking import tracking_pixel, link_click
from .views.message_template import MessageTemplateListView

urlpatterns = [
    path('telegram/<int:bot_id>', telegram_webhook),
    path('whatsapp', whatsapp_webhook),
    path('e/p/<uuid:tracking_id>/', tracking_pixel, name='e_px'),
    path('e/l/<uuid:tracking_id>/<int:link_index>/', link_click, name='e_lc'),
    path('api/message-templates/', MessageTemplateListView.as_view(), name='message_templates'),
]
