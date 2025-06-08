from django.urls import path
from unicom.views.telegram_webhook import telegram_webhook
from unicom.views.whatsapp_webhook import whatsapp_webhook
from unicom.views.email_tracking import tracking_pixel, link_click
from .views.message_template import MessageTemplateListView, populate_message_template
from unicom.views.inline_image import serve_inline_image
from unicom.views.inline_image import serve_template_inline_image

urlpatterns = [
    path('telegram/<int:bot_id>', telegram_webhook),
    path('whatsapp', whatsapp_webhook),
    path('e/p/<uuid:tracking_id>/', tracking_pixel, name='e_px'),
    path('e/l/<uuid:tracking_id>/<int:link_index>/', link_click, name='e_lc'),
    path('api/message-templates/', MessageTemplateListView.as_view(), name='message_templates'),
    path('api/message-templates/populate/', populate_message_template, name='populate_message_template'),
    path('i/<str:shortid>/', serve_inline_image, name='inline_image'),
    path('t/<str:shortid>/', serve_template_inline_image, name='template_inline_image'),
]
