"""
ASGI config for unicom_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import logging
import os

from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

logger = logging.getLogger("asgi")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unicom_project.settings')

# Base HTTP application (works even when Channels is missing)
django_application = get_asgi_application()
if settings.DEBUG:
    django_application = ASGIStaticFilesHandler(django_application)

try:
    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter
    from django.urls import path
    from unicom.consumers import WebChatConsumer
    websocket_urlpatterns = [
        path("ws/unicom/webchat/<str:chat_id>/", WebChatConsumer.as_asgi()),
        path("ws/unicom/webchat/<str:chat_id>", WebChatConsumer.as_asgi()),
    ]
    application = ProtocolTypeRouter({
        "http": django_application,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    })
    logger.warning("Channels routing ENABLED")
except Exception as e:
    logger.exception("Channels routing DISABLED — falling back to HTTP-only")
    application = django_application
