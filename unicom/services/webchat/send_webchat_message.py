"""
Send outgoing WebChat messages (from bots/system to users).
"""
from django.apps import apps
from django.utils import timezone
from django.core.files import File


def send_webchat_message(channel, msg, user=None):
    """
    Send a WebChat message (save to database).
    Used by bots/system to send messages to users.

    Args:
        channel: WebChat Channel instance
        msg: Dict with message details
            {
                'chat_id': str,  # Required
                'text': str,  # Required (or html)
                'html': str,  # Optional - rich HTML content
                'file_path': str,  # Optional - path to media file
                'media_type': str,  # 'text', 'html', 'image', 'audio'
            }
        user: User instance (optional)

    Returns:
        Message instance
    """
    Message = apps.get_model('unicom', 'Message')
    Chat = apps.get_model('unicom', 'Chat')
    Account = apps.get_model('unicom', 'Account')
    AccountChat = apps.get_model('unicom', 'AccountChat')

    platform = 'WebChat'

    # Get required fields
    chat_id = msg.get('chat_id')
    if not chat_id:
        raise ValueError("chat_id is required")

    text = msg.get('text', '').strip()
    html = msg.get('html', '').strip()

    if not text and not html:
        raise ValueError("Either text or html is required")

    # Get chat
    try:
        chat = Chat.objects.get(id=chat_id, platform=platform)
    except Chat.DoesNotExist:
        raise ValueError(f"Chat {chat_id} not found")

    # Get sender account (system/bot account)
    # For WebChat, outgoing messages are from the channel's "bot" account
    sender_account_id = f"webchat_bot_{channel.id}"
    sender_account, created = Account.objects.get_or_create(
        id=sender_account_id,
        defaults={
            'platform': platform,
            'channel': channel,
            'name': channel.name,
            'is_bot': True,
            'raw': {'channel_id': channel.id}
        }
    )

    # Determine media type
    media_type = msg.get('media_type', 'html' if html else 'text')

    # Generate message ID
    import uuid
    message_id = f"webchat_{chat_id}_{uuid.uuid4()}"

    # Create message
    message = Message(
        id=message_id,
        channel=channel,
        platform=platform,
        sender=sender_account,
        user=user,
        chat=chat,
        is_outgoing=True,  # Outgoing message to user
        sender_name=sender_account.name,
        text=text or html,
        html=html if html else None,
        media_type=media_type,
        timestamp=timezone.now(),
        raw={
            'source': 'webchat_outgoing',
            'channel_id': channel.id,
            'user_id': user.id if user else None,
        }
    )

    # Handle media file
    file_path = msg.get('file_path')
    if file_path:
        try:
            with open(file_path, 'rb') as f:
                file_content = File(f)
                import os
                filename = os.path.basename(file_path)
                message.media.save(filename, file_content, save=False)
        except Exception as e:
            print(f"Warning: Could not attach media file: {e}")

    message.save()

    # Handle interactive buttons
    buttons = msg.get('buttons')
    if buttons:
        from unicom.models import CallbackExecution, AccountChat
        
        # Get intended account (recipient)
        account_chat = AccountChat.objects.filter(chat=chat).first()
        intended_account = account_chat.account if account_chat else None
        
        if intended_account:
            # Process buttons and create CallbackExecution records
            processed_buttons = []
            for row in buttons:
                processed_row = []
                for button in row:
                    if button.get('type') == 'callback':
                        execution = CallbackExecution.objects.create(
                            original_message=message,
                            callback_data=button['callback_data'],
                            intended_account=intended_account,
                            expires_at=button.get('expires_at')
                        )
                        button = button.copy()
                        button['callback_execution_id'] = str(execution.id)
                    processed_row.append(button)
                processed_buttons.append(processed_row)
            
            # Store in message raw data
            if not message.raw:
                message.raw = {}
            message.raw['interactive_buttons'] = processed_buttons
            message.save(update_fields=['raw'])

    # Update chat cache fields
    if not chat.first_message:
        chat.first_message = message
    if not chat.first_outgoing_message:
        chat.first_outgoing_message = message
    chat.last_message = message
    chat.last_outgoing_message = message
    chat.save(update_fields=[
        'first_message', 'first_outgoing_message',
        'last_message', 'last_outgoing_message'
    ])

    return message
