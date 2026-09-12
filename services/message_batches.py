"""Persist an explicit incoming turn without assuming provider album semantics."""

from django.db import transaction


def save_incoming_message_batch(messages):
    """Save one completed adapter-supplied group; the caller queues its final message.

    Each item remains an ordinary single-media Message. Channel adapters must
    authenticate senders, decide group completeness and deduplicate provider
    events before calling this function. No outgoing delivery is performed.
    """
    messages = list(messages)
    if not messages:
        raise ValueError("An incoming batch must contain at least one message")
    first = messages[0]
    identity = (first.channel_id, first.platform, first.chat_id, first.sender_id, first.user_id)
    ids = set()
    for message in messages:
        if not message._state.adding or not message.pk or message.pk in ids:
            raise ValueError("Batch messages must be new and have distinct ids")
        ids.add(message.pk)
        if message.is_outgoing is not False:
            raise ValueError("Only incoming messages can form an incoming batch")
        if (message.channel_id, message.platform, message.chat_id, message.sender_id, message.user_id) != identity:
            raise ValueError("Batch messages must share channel, chat and sender")
    with transaction.atomic():
        chat = first.chat.__class__.objects.select_for_update().get(pk=first.chat_id)
        if chat.channel_id != first.channel_id or chat.platform != first.platform:
            raise ValueError("The chat must belong to the batch channel and platform")
        parent = first.reply_to_message
        if parent is not None and parent.chat_id != first.chat_id:
            raise ValueError("The batch parent must belong to its chat")
        for message in messages:
            message.reply_to_message = parent
            message.raw = {**(message.raw or {}), "skip_request_creation": True}
            message.save(force_insert=True)
            parent = message
    return messages
