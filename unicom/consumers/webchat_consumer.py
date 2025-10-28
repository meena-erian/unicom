"""
Lightweight WebChat WebSocket consumer.

This consumer keeps a WebSocket connection per chat and periodically checks for
new messages directly from the database. When it finds new messages it pushes
them to the connected client, eliminating the need for the browser to issue
HTTP polling requests every few seconds.

Installation (only needed if you plan to enable websockets):

    pip install channels

Minimal ASGI routing example:

    from django.urls import path
    from unicom.consumers.webchat_consumer import WebChatConsumer

    websocket_urlpatterns = [
        path('ws/unicom/webchat/<str:chat_id>/', WebChatConsumer.as_asgi()),
    ]
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

try:
    from channels.generic.websocket import AsyncJsonWebsocketConsumer
    from channels.db import database_sync_to_async

    CHANNELS_AVAILABLE = True
except ImportError:  # pragma: no cover - channels is optional
    CHANNELS_AVAILABLE = False

    class AsyncJsonWebsocketConsumer:  # type: ignore
        """Fallback stub so imports do not fail when channels is missing."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Django Channels is required to use the WebChat WebSocket consumer. "
                "Install it with: pip install channels"
            )

    def database_sync_to_async(func):  # type: ignore
        return func


@dataclass
class _SerializedMessage:
    message_id: str
    payload: dict


class WebChatConsumer(AsyncJsonWebsocketConsumer):
    """
    Extremely small WebChat consumer that:
    - Accepts ``ws/unicom/webchat/<chat_id>/`` connections.
    - Verifies the authenticated/guest account can access the requested chat.
    - Checks the database every five seconds without sending network traffic.
    - Emits ``{"type": "new_message", "chat_id": ..., "message": {...}}`` only
      when new messages exist.

    The consumer does not depend on channel layers and therefore works with the
    default in-memory Channels backend, keeping unicom's package easy to ship.
    """

    poll_interval_seconds = 5
    warm_cache_limit = 100

    def __init__(self, *args, **kwargs):
        if not CHANNELS_AVAILABLE:  # pragma: no cover - handled above
            raise ImportError(
                "Django Channels is not installed. Install it with: pip install channels"
            )
        super().__init__(*args, **kwargs)

        self.chat_id: Optional[str] = None
        self.account = None
        self._polling_task: Optional[asyncio.Task] = None
        self._recent_ids = deque(maxlen=self.warm_cache_limit)
        self._recent_id_set: set[str] = set()

    # ------------------------------------------------------------------ WS API
    async def connect(self):
        """Validate access and start background polling."""
        self.chat_id = self._extract_chat_id()
        if not self.chat_id:
            await self.close(code=4400)  # bad request
            return

        try:
            self.account = await self._get_account()
        except ValueError:
            await self.close(code=4401)  # unable to resolve account
            return

        has_access = await self._account_has_chat_access(self.chat_id)
        if not has_access:
            await self.close(code=4403)  # forbidden
            return

        await self.accept()
        await self._warm_seen_cache()
        await self.send_json({"type": "ready", "chat_id": self.chat_id})

        # Start the periodic polling task.
        self._polling_task = asyncio.create_task(self._poll_for_updates())

    async def disconnect(self, code):
        """Stop background polling gracefully."""
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

    async def receive_json(self, content, **kwargs):
        """
        No client commands are required for this consumer. Respond to optional
        heartbeats so the caller knows the connection is alive.
        """
        if content.get("action") == "ping":
            await self.send_json({"type": "pong"})

    # -------------------------------------------------------------- Polling loop
    async def _poll_for_updates(self):
        """
        Periodically check the database for new messages. Only messages that
        have not been seen before are pushed to the client.
        """
        try:
            while True:
                await asyncio.sleep(self.poll_interval_seconds)
                pending = await self._get_recent_messages()
                fresh = self._filter_fresh_messages(pending)
                if not fresh:
                    continue

                for item in fresh:
                    await self.send_json(
                        {
                            "type": "new_message",
                            "chat_id": self.chat_id,
                            "message": item.payload,
                        }
                    )
                    self._remember_message_id(item.message_id)
        except asyncio.CancelledError:
            # Task cancelled on disconnect – nothing else to do.
            return

    # -------------------------------------------------------------- Cache utils
    def _extract_chat_id(self) -> Optional[str]:
        route = self.scope.get("url_route") or {}
        kwargs = route.get("kwargs") or {}
        return kwargs.get("chat_id")

    async def _warm_seen_cache(self):
        """
        Record the IDs of the most recent messages so the consumer does not
        resend historical data immediately after connecting.
        """
        recent_ids = await self._get_recent_message_ids()
        for message_id in recent_ids:
            self._remember_message_id(message_id)

    def _filter_fresh_messages(
        self, messages: Iterable[_SerializedMessage]
    ) -> list[_SerializedMessage]:
        """Return only messages that have not been delivered yet."""
        fresh = []
        for item in messages:
            if item.message_id in self._recent_id_set:
                continue
            fresh.append(item)
        return fresh

    def _remember_message_id(self, message_id: str):
        """Track delivered messages and keep the cache bounded."""
        if message_id in self._recent_id_set:
            return

        self._recent_id_set.add(message_id)
        self._recent_ids.append(message_id)

        # Keep the backing set aligned with the deque window.
        while len(self._recent_id_set) > len(self._recent_ids):
            oldest = self._recent_ids.popleft()
            self._recent_id_set.discard(oldest)

    # --------------------------------------------------------- DB interactions
    @database_sync_to_async
    def _get_account(self):
        from django.apps import apps
        from unicom.services.webchat.get_or_create_account import get_or_create_account

        Channel = apps.get_model("unicom", "Channel")
        channel = Channel.objects.filter(platform="WebChat", active=True).first()
        if not channel:
            raise ValueError("No active WebChat channel found for WebChat platform.")

        class ScopeRequest:
            def __init__(self, scope):
                self.user = scope.get("user")
                self.session = scope.get("session")

        request_like = ScopeRequest(self.scope)
        return get_or_create_account(channel, request_like)

    @database_sync_to_async
    def _account_has_chat_access(self, chat_id: str) -> bool:
        from django.apps import apps

        Chat = apps.get_model("unicom", "Chat")
        AccountChat = apps.get_model("unicom", "AccountChat")

        try:
            chat = Chat.objects.get(id=chat_id, platform="WebChat")
        except Chat.DoesNotExist:
            return False

        return AccountChat.objects.filter(account=self.account, chat=chat).exists()

    @database_sync_to_async
    def _get_recent_message_ids(self) -> list[str]:
        """
        Fetch IDs for the most recent messages so the cache can be primed on
        connection. IDs are returned in chronological order.
        """
        from django.apps import apps

        Message = apps.get_model("unicom", "Message")
        qs = (
            Message.objects.filter(chat_id=self.chat_id, platform="WebChat")
            .order_by("-timestamp")
            .values_list("id", flat=True)[: self.warm_cache_limit]
        )
        result = list(qs)
        result.reverse()
        return result

    @database_sync_to_async
    def _get_recent_messages(self) -> Tuple[_SerializedMessage, ...]:
        """
        Retrieve a bounded window of recent messages (chronological order).
        Returning a tuple keeps the result immutable for the async caller.
        """
        from django.apps import apps

        Message = apps.get_model("unicom", "Message")
        messages = list(
            Message.objects.filter(chat_id=self.chat_id, platform="WebChat")
            .order_by("-timestamp")[: self.warm_cache_limit]
        )
        messages.reverse()

        serialized = tuple(
            _SerializedMessage(message_id=msg.id, payload=self._serialize_message(msg))
            for msg in messages
        )
        return serialized

    # ------------------------------------------------------------- Serialization
    def _serialize_message(self, message) -> dict:
        """Convert a Message model instance into the JSON payload expected by JS."""
        return {
            "id": message.id,
            "text": message.text,
            "html": message.html,
            "is_outgoing": message.is_outgoing,
            "sender_name": message.sender_name,
            "timestamp": message.timestamp.isoformat(),
            "media_type": message.media_type,
            "media_url": message.media.url if message.media else None,
            "reply_to_message_id": message.reply_to_message_id if message.reply_to_message else None,
            "interactive_buttons": message.raw.get('interactive_buttons') if message.raw else None,
        }


def is_channels_available() -> bool:
    """Helper so callers can check if Channels is installed."""
    return CHANNELS_AVAILABLE


async def broadcast_message_to_chat(chat_id: str, message) -> None:
    """
    Legacy helper retained for backwards compatibility.

    The simplified consumer no longer relies on channel layers, so this helper
    simply exists to avoid import errors in projects that may still reference
    it. Messages are delivered by the consumer's periodic polling loop instead.
    """
    return None
