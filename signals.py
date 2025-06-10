from unicom.models import Message, AccountChat, Channel, Request
from django.db import transaction
from django.db.models.signals import post_save, pre_save, post_delete
from unicom.services.email.IMAP_thread_manager import imap_manager
from unicom.services.chat_summary import update_chat_summary
from django.db import transaction
from django.dispatch import receiver
import threading
from django.utils import timezone
import logging
from imapclient import IMAPClient, SEEN
import imaplib




@receiver(pre_save, sender=Channel)
def channel_pre_save(sender, instance, **kwargs):
    # Save old config for comparison in post_save
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_config = old.config
        except sender.DoesNotExist:
            instance._old_config = None


@receiver(post_save, sender=Channel)
def run_channel_after_insert(sender, instance, created, **kwargs):
    # Check if created or config changed
    def validate_and_then_start():
        instance.validate()
        imap_manager.restart(instance)
    config_changed = not created and getattr(instance, '_old_config', None) != instance.config
    if created or config_changed:
        transaction.on_commit(lambda: threading.Thread(target=validate_and_then_start).start())
 
@receiver(post_delete, sender=Channel)
def run_channel_after_delete(sender, instance, **kwargs):
    # Stop the IMAP listener thread for the channel
    imap_manager.stop(instance)
    print(f"Channel {instance.pk} deleted, IMAP listener stopped.")


@receiver(post_save, sender=Message)
def create_request_from_message(sender, instance, created, **kwargs):
    """
    Signal handler to create a Request object when a new Message is created.
    Only creates a Request for incoming messages (is_outgoing=False).
    """
    if not created:
        return

    # Update chat summary fields
    update_chat_summary(instance)
    
    # Skip request creation if it's an outgoing message
    if instance.is_outgoing:
        return

    # Extract contact information based on platform
    email = None
    phone = None
    
    if instance.sender:
        if instance.platform == 'Email':
            email = instance.sender.id
        elif instance.platform == 'WhatsApp':
            phone = instance.sender.id

    try:
        with transaction.atomic():
            # Create the request object using the instance directly
            request = Request.objects.create(
                message=instance,
                account=instance.sender,
                channel=instance.channel,
                email=email,
                phone=phone,
                display_text=instance.text,
                status='PENDING',
                metadata={
                    'created_from': 'message_signal',
                    'message_platform': instance.platform,
                    'creation_time': timezone.now().isoformat(),
                }
            )

            # Try to identify member
            request.identify_member()
            
            # Always proceed to categorization regardless of member identification
            request.categorize()

    except Exception as e:
        # Log the error but don't re-raise to avoid affecting message creation
        error_msg = f"Error creating request from message {instance.id}: {str(e)}"
        print(error_msg)
        logger = logging.getLogger(__name__)
        logger.error(error_msg, exc_info=True)

@receiver(post_save, sender=Request)
def mark_email_seen_on_request_completed(sender, instance, **kwargs):
    """
    When a Request is marked as COMPLETED, and the related Message is an email, and the channel's MARK_SEEN_WHEN is 'on_request_completed',
    connect to IMAP and mark the message as seen using the Message ID (IMAP UID).
    """
    if instance.status != 'COMPLETED':
        return
    msg = instance.message
    channel = instance.channel
    if not (msg and channel and msg.platform == 'Email'):
        return
    mark_seen_when = channel.config.get('MARK_SEEN_WHEN', 'never').lower()
    if mark_seen_when != 'on_request_completed':
        return
    # Get IMAP config
    imap_conf = channel.config.get('IMAP', {})
    host = imap_conf.get('host')
    port = imap_conf.get('port')
    use_ssl = imap_conf.get('use_ssl')
    email_address = channel.config.get('EMAIL_ADDRESS')
    password = channel.config.get('EMAIL_PASSWORD')
    if not all([host, port, email_address, password]):
        return
    # The Message ID is the IMAP UID
    uid = msg.id
    try:
        with IMAPClient(host, port=port, ssl=use_ssl) as server:
            server.login(email_address, password)
            server.select_folder('INBOX')
            # Mark as seen
            server.add_flags(uid, [SEEN])
            logger = logging.getLogger(__name__)
            logger.info(f"Marked email as seen for Message ID/UID {uid} on channel {channel.pk}")
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to mark email as seen for Message ID/UID {uid} on channel {channel.pk}: {e}")