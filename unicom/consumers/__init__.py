"""
Unicom WebSocket Consumers (Optional - requires Django Channels)
"""

# Only import if channels is available
try:
    from .webchat_consumer import WebChatConsumer, is_channels_available, broadcast_message_to_chat
    __all__ = ['WebChatConsumer', 'is_channels_available', 'broadcast_message_to_chat']
except ImportError:
    # Channels not available - that's okay, we'll use polling
    __all__ = []
