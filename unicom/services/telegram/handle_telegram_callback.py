# unicom.services.telegram.handle_telegram_callback.py
from __future__ import annotations
from typing import TYPE_CHECKING
from django.db import transaction
from unicom.models import CallbackExecution, Message, Account
from unicom.signals import telegram_callback_received
from unicom.services.telegram.answer_callback_query import answer_callback_query
import logging

if TYPE_CHECKING:
    from unicom.models import Channel

logger = logging.getLogger(__name__)


def handle_telegram_callback(channel: Channel, callback_query_data: dict):
    """
    Handle Telegram callback query (button click) with automatic security validation
    and idempotency across multiple Django processes.

    Args:
        channel: The Telegram channel
        callback_query_data: Telegram callback query data including:
            - id: Unique callback query ID
            - data: Button callback data
            - from: User who clicked the button
            - message: The message containing the buttons

    Returns:
        bool: True if callback was processed, False if ignored/already processed
    """
    callback_id = callback_query_data.get('id')
    callback_data = callback_query_data.get('data')
    from_user = callback_query_data.get('from', {})
    message_data = callback_query_data.get('message', {})

    print(f"🔘 CALLBACK DEBUG: Received callback query")
    print(f"   - Callback ID: {callback_id}")
    print(f"   - Callback Data: {callback_data}")
    print(f"   - From User: {from_user.get('id')} (@{from_user.get('username')})")
    print(f"   - Message ID: {message_data.get('message_id')}")

    # Answer callback query immediately to stop loading indicator
    print(f"📞 CALLBACK DEBUG: Answering callback query to stop loading indicator")
    answer_callback_query(channel, callback_id)

    if not all([callback_id, callback_data, from_user, message_data]):
        logger.warning(f"Invalid callback query data: missing required fields")
        print(f"❌ CALLBACK DEBUG: Missing required fields")
        return False

    # Get the original message containing the buttons
    original_message_id = message_data.get('message_id')  # Keep as integer
    print(f"🔍 CALLBACK DEBUG: Looking for original message with ID: {original_message_id} (type: {type(original_message_id)})")
    try:
        original_message = Message.objects.get(
            platform='Telegram',
            channel=channel,
            raw__message_id=original_message_id
        )
        print(f"✅ CALLBACK DEBUG: Found original message: {original_message.id}")
    except Message.DoesNotExist:
        logger.warning(f"Original message not found for callback: {original_message_id}")
        print(f"❌ CALLBACK DEBUG: Original message not found for ID: {original_message_id}")
        return False

    # Get the user account who clicked the button
    user_id = str(from_user.get('id'))
    print(f"🔍 CALLBACK DEBUG: Looking for user account with ID: {user_id}")
    try:
        clicking_user = Account.objects.get(id=user_id, platform='Telegram')
        username = clicking_user.raw.get('username', clicking_user.name)
        print(f"✅ CALLBACK DEBUG: Found user account: {username} (name: {clicking_user.name})")
    except Account.DoesNotExist:
        logger.warning(f"Account not found for user: {user_id}")
        print(f"❌ CALLBACK DEBUG: Account not found for user: {user_id}")
        return False

    # Security check: Only the original recipient can click buttons
    # This prevents abuse in group chats or forwarded messages
    print(f"🔒 CALLBACK DEBUG: Checking authorization for button click")
    if not is_authorized_to_click_button(original_message, clicking_user):
        logger.info(f"Unauthorized button click by {username} on message {original_message.id}")
        print(f"❌ CALLBACK DEBUG: Unauthorized button click by {username}")
        return False
    print(f"✅ CALLBACK DEBUG: User is authorized to click button")

    # Atomic check-and-process to ensure single execution
    print(f"🔄 CALLBACK DEBUG: Starting atomic callback processing")
    with transaction.atomic():
        execution, created = CallbackExecution.objects.select_for_update().get_or_create(
            callback_id=callback_id,
            defaults={
                'callback_message': create_callback_message(callback_query_data, original_message, clicking_user),
                'original_message': original_message,
                'callback_data': callback_data,
                'authorized_user': clicking_user,
            }
        )

        if not created:
            # Already processed by another process
            logger.debug(f"Callback {callback_id} already processed")
            print(f"⚠️ CALLBACK DEBUG: Callback {callback_id} already processed (idempotency protection)")
            return False

        print(f"✅ CALLBACK DEBUG: Created new CallbackExecution with ID: {execution.id}")

        # Fire signal for project handlers - they get a complete execution context
        try:
            print(f"📡 CALLBACK DEBUG: Firing telegram_callback_received signal")
            telegram_callback_received.send(
                sender=handle_telegram_callback,
                callback_execution=execution
            )
            print(f"✅ CALLBACK DEBUG: Signal fired successfully")

            # Mark as processed after successful signal handling
            execution.mark_processed()
            logger.info(f"Successfully processed callback {callback_id}: {callback_data}")
            print(f"🎉 CALLBACK DEBUG: Successfully processed callback {callback_id}: {callback_data}")
            return True

        except Exception as e:
            # Check if it's a network error
            error_str = str(e)
            if 'Connection' in error_str or 'Timeout' in error_str or 'timed out' in error_str:
                logger.warning(f"Network error processing callback {callback_id}: {error_str}")
                print(f"⚠️ CALLBACK DEBUG: Network error processing callback {callback_id}")
                print(f"   The callback was received but couldn't send response due to network issues")
                # Still mark as processed since we executed the handler
                execution.mark_processed()
                return True
            else:
                logger.error(f"Error processing callback {callback_id}: {str(e)}", exc_info=True)
                print(f"❌ CALLBACK DEBUG: Error processing callback {callback_id}: {str(e)}")
                # Don't mark as processed so it can be retried
                return False


def is_authorized_to_click_button(original_message: Message, clicking_user: Account) -> bool:
    """
    Security check to ensure only authorized users can click buttons.
    Prevents abuse in group chats, forwarded messages, etc.

    Args:
        original_message: The message containing the buttons
        clicking_user: The user who clicked the button

    Returns:
        bool: True if user is authorized to click buttons on this message
    """
    # Rule 1: If it's a private chat, only the chat participant can click
    if original_message.chat.id.startswith('private_'):
        # Extract user ID from private chat ID (format: "private_{user_id}")
        authorized_user_id = original_message.chat.id.replace('private_', '')
        return clicking_user.id == authorized_user_id

    # Rule 2: If it's an outgoing message in any chat, only the original recipient can click
    if original_message.is_outgoing:
        # For outgoing messages, the chat participant (not the sender) is authorized
        return clicking_user.id != original_message.sender.id

    # Rule 3: For incoming messages in groups, only the original sender can click their own buttons
    return clicking_user.id == original_message.sender.id


def create_callback_message(callback_query_data: dict, original_message: Message, clicking_user: Account) -> Message:
    """
    Create a Message object representing the callback button click.
    This allows projects to use familiar message.reply_with() patterns.
    """
    from unicom.services.telegram.save_telegram_message import save_telegram_message

    # Create a minimal message-like structure for the callback
    callback_message_data = {
        'message_id': f"callback_{callback_query_data['id']}",
        'from': callback_query_data['from'],
        'chat': callback_query_data['message']['chat'],
        'date': callback_query_data.get('date', callback_query_data['message']['date']),
        'text': f"[Button clicked: {callback_query_data['data']}]"
    }

    # Save as a special callback message
    callback_message = save_telegram_message(
        original_message.channel,
        callback_message_data,
        user=None  # This is a system-generated message
    )

    # Mark it as a callback type and link to original
    callback_message.media_type = 'callback'
    callback_message.reply_to_message = original_message
    callback_message.save(update_fields=['media_type', 'reply_to_message'])

    return callback_message