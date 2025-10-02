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
    Handle Telegram callback query (button click).

    Args:
        channel: The Telegram channel
        callback_query_data: Telegram callback query data including:
            - id: Unique callback query ID
            - data: CallbackExecution ID
            - from: User who clicked the button
            - message: The message containing the buttons

    Returns:
        bool: True if callback was processed, False if ignored
    """
    callback_id = callback_query_data.get('id')
    callback_execution_id = callback_query_data.get('data')
    from_user = callback_query_data.get('from', {})
    message_data = callback_query_data.get('message', {})

    print(f"🔘 CALLBACK DEBUG: Received callback query")
    print(f"   - Callback ID: {callback_id}")
    print(f"   - CallbackExecution ID: {callback_execution_id}")
    print(f"   - From User: {from_user.get('id')} (@{from_user.get('username')})")

    # Answer callback query immediately to stop loading indicator
    print(f"📞 CALLBACK DEBUG: Answering callback query to stop loading indicator")
    answer_callback_query(channel, callback_id)

    if not all([callback_id, callback_execution_id, from_user]):
        logger.warning(f"Invalid callback query data: missing required fields")
        print(f"❌ CALLBACK DEBUG: Missing required fields")
        return False

    # Lookup CallbackExecution
    try:
        execution = CallbackExecution.objects.select_related(
            'original_message', 'intended_account'
        ).get(id=callback_execution_id)
        print(f"✅ CALLBACK DEBUG: Found CallbackExecution: {execution.id}")
    except CallbackExecution.DoesNotExist:
        logger.warning(f"CallbackExecution not found: {callback_execution_id}")
        print(f"❌ CALLBACK DEBUG: CallbackExecution not found")
        return False

    # Check if expired
    if execution.is_expired():
        logger.info(f"CallbackExecution {execution.id} has expired")
        print(f"⏰ CALLBACK DEBUG: CallbackExecution has expired")
        return False

    # Get the clicking account
    user_id = str(from_user.get('id'))
    print(f"🔍 CALLBACK DEBUG: Looking for clicking account with ID: {user_id}")
    try:
        clicking_account = Account.objects.get(id=user_id, platform='Telegram')
        username = clicking_account.raw.get('username', clicking_account.name)
        print(f"✅ CALLBACK DEBUG: Found clicking account: {username}")
    except Account.DoesNotExist:
        logger.warning(f"Account not found for user: {user_id}")
        print(f"❌ CALLBACK DEBUG: Account not found")
        return False

    # Security check: Only the intended account can click
    if clicking_account.id != execution.intended_account.id:
        logger.info(f"Unauthorized button click by {username} on callback {execution.id}")
        print(f"❌ CALLBACK DEBUG: Account {username} is not the intended account")
        return False
    print(f"✅ CALLBACK DEBUG: Account is authorized")

    # Create callback message
    callback_message = create_callback_message(
        callback_query_data,
        execution.original_message,
        clicking_account
    )

    # Fire signal for project handlers
    try:
        print(f"📡 CALLBACK DEBUG: Firing telegram_callback_received signal")
        telegram_callback_received.send(
            sender=handle_telegram_callback,
            callback_execution=execution,
            callback_message=callback_message
        )
        print(f"✅ CALLBACK DEBUG: Signal fired successfully")
        logger.info(f"Successfully processed callback {callback_id}")
        return True

    except Exception as e:
        logger.error(f"Error processing callback {callback_id}: {str(e)}", exc_info=True)
        print(f"❌ CALLBACK DEBUG: Error processing callback: {str(e)}")
        return False


def create_callback_message(callback_query_data: dict, original_message: Message, clicking_account: Account) -> Message:
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
        'text': f"[Button clicked]"
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