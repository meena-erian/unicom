"""Trusted, channel-selected presentation for HTTP and realtime consumers."""

from django.conf import settings
from django.utils.module_loading import import_string

from unicom.services.message_serialization import serialize_message


def get_message_presenter(channel):
    configured = getattr(settings, "UNICOM_WEBCHAT_MESSAGE_PRESENTERS", {})
    presenter = configured.get(str(channel.pk)) if channel is not None else None
    if isinstance(presenter, str):
        presenter = import_string(presenter)
    if presenter is not None and not callable(presenter):
        raise TypeError("A WebChat message presenter must be callable")
    return presenter


def serialize_webchat_message(message, *, viewer=None):
    return serialize_message(message, presenter=get_message_presenter(message.channel), viewer=viewer)
