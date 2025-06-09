from __future__ import annotations
from typing import TYPE_CHECKING
from django.conf import settings
from django.core.mail import get_connection
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from fa2svg.converter import to_inline_png_img, revert_to_original_fa
from unicom.services.email.save_email_message import save_email_message
from unicom.services.email.email_tracking import prepare_email_for_tracking, remove_tracking
from unicom.services.get_public_origin import get_public_domain
from django.apps import apps
import logging
from email.utils import make_msgid
import uuid
import html
from unicom.services.html_inline_images import html_shortlinks_to_base64_images, html_base64_images_to_shortlinks

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from unicom.models import Channel


def convert_text_to_html(text: str) -> str:
    """
    Convert plain text to HTML while preserving formatting.
    Uses <pre> tag to maintain whitespace and newlines.
    Only escapes HTML special characters for security.
    """
    if not text:
        return ""
    
    # Escape HTML special characters
    escaped_text = html.escape(text)
    
    # Wrap in pre tag to preserve formatting
    return f'<pre style="margin: 0; white-space: pre-wrap; word-wrap: break-word;">{escaped_text}</pre>'


def send_email_message(channel: Channel, params: dict, user: User=None):
    """
    Compose, send and save an email using the SMTP/IMAP credentials
    configured on ``channel``.

    The function handles both new email threads and replies:
    
    For new threads:
        - Must provide 'to' list with at least one recipient
        - Must provide 'subject' for the email
        - A new Chat will be created with the sent email's Message-ID
    
    For replies (either option):
        - Option 1: Provide 'chat_id' of an existing email thread
          The last message in the chat will be used as reference
        - Option 2: Provide 'reply_to_message_id' of a specific message
          The referenced message will be used directly
        - Recipients are derived from the original thread unless overridden
        - Subject is derived from parent message if not provided

    Parameters
    ----------
    channel : unicom.models.Channel
        Channel whose ``config`` dictionary supplies ``EMAIL_ADDRESS``,
        ``EMAIL_PASSWORD``, ``SMTP`` and ``IMAP`` settings.
    params : dict
        to       (list[str], required for new threads) – primary recipient addresses
        subject  (str, required for new threads) – subject line for new threads
        chat_id  (str, optional) – ID of existing email thread to reply to
        reply_to_message_id (str, optional) – specific message ID to reply to
        text     (str, optional) – plain-text body
        html     (str, optional) – HTML body. If omitted but *text* is
                                   supplied, it is generated automatically
        cc, bcc (list[str], optional) – additional recipient addresses
        attachments (list[str], optional) – absolute paths of files to attach
    user : django.contrib.auth.models.User, optional
        User responsible for the action

    Returns
    -------
    unicom.models.Message
        The persisted database record representing the sent email.

    Raises
    ------
    ValueError
        - If neither 'to' (new thread) nor 'chat_id'/'reply_to_message_id' (reply) is provided
        - If chat_id is provided but chat doesn't exist or has no messages
        - If reply_to_message_id is provided but message doesn't exist
        - If starting a new thread without a subject
    """
    Message = apps.get_model('unicom', 'Message')
    Chat = apps.get_model('unicom', 'Chat')
    from_addr = channel.config['EMAIL_ADDRESS']
    smtp_conf = channel.config['SMTP']
    connection = get_connection(
        host=smtp_conf['host'],
        port=smtp_conf['port'],
        username=from_addr,
        password=channel.config['EMAIL_PASSWORD'],
        use_ssl=smtp_conf['use_ssl'],
    )

    # Determine message context (new thread vs reply)
    chat_id = params.get('chat_id')
    reply_to_id = params.get('reply_to_message_id')
    to_addrs = params.get('to', [])
    parent = None
    
    # Case 1: Reply to specific message
    if reply_to_id:
        parent = Message.objects.get(id=reply_to_id)
        if not parent:
            raise ValueError(f"Reply-to message not found: {reply_to_id}")
        
    # Case 2: Reply in chat thread
    elif chat_id:
        chat = Chat.objects.get(id=chat_id)
        if not chat:
            raise ValueError(f"Email chat not found: {chat_id}")
            
        parent = chat.messages.filter(
            is_outgoing=False
        ).order_by('-timestamp').first()
        
        if not parent:
            parent = chat.messages.filter(
                is_outgoing=True
            ).order_by('-timestamp').first()
            if not parent:
                raise ValueError(f"No messages found in chat {chat_id} to reply to")
            
    # Case 3: New thread
    elif to_addrs:
        # Validate subject is provided for new threads
        if not params.get('subject'):
            raise ValueError("Subject is required when starting a new email thread")
        cc_addrs = params.get('cc', [])
        bcc_addrs = params.get('bcc', [])
    else:
        raise ValueError("Must provide either 'to' addresses for new thread, or 'chat_id'/'reply_to_message_id' for reply")

    # If this is a reply, use parent message for threading and recipients
    if parent:
        # Use original recipients if not explicitly overridden
        to_addrs = to_addrs or parent.to
        cc_addrs = params.get('cc', parent.cc)
        bcc_addrs = params.get('bcc', parent.bcc)
        reply_to_id = parent.id  # Ensure we have the message ID for threading

    logger.info(f"Preparing to send email: to={to_addrs}, cc={cc_addrs}, bcc={bcc_addrs}")

    # Build subject (fall back to "Re: <original>")
    subject = params.get('subject')
    if not subject and params.get('reply_to_message_id'):
        parent = Message.objects.filter(id=params['reply_to_message_id']).first()
        if parent:
            # Remove any existing "Re: " prefixes and add just one
            base = parent.subject or ""
            while base.lower().startswith("re: "):
                base = base[4:]
            subject = "Re: " + base
            logger.debug(f"Created reply subject: {subject} (based on parent: {parent.subject})")
        else:
            subject = ""
            logger.warning(f"Reply-to message not found: {params['reply_to_message_id']}")

    # Generate a message ID and tracking ID before constructing the message
    message_id = make_msgid(domain=get_public_domain())
    tracking_id = uuid.uuid4()
    logger.info(f"Generated Message-ID: {message_id}, Tracking-ID: {tracking_id}")

    # Handle HTML content
    text_content = params.get('text', '')
    html_content = params.get('html')
    
    # If HTML is not provided but text is, convert text to HTML
    if not html_content and text_content:
        html_content = convert_text_to_html(text_content)
        logger.debug("Converted plain text to HTML")

    # Add tracking
    if html_content:
        html_content = to_inline_png_img(html_content)  # Convert FontAwesome to inline images

    # Prepare HTML content with tracking
    original_urls = []
    if html_content:
        html_content, original_urls = prepare_email_for_tracking(html_content, tracking_id)
        logger.debug("Added tracking elements to HTML content")

    # --- Convert shortlinks to base64 for sending ---
    html_content_for_sending = html_shortlinks_to_base64_images(html_content) if html_content else html_content

    # 1) construct the EmailMultiAlternatives
    email_msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_addr,
        to=to_addrs,
        cc=cc_addrs,
        bcc=bcc_addrs,
        connection=connection,
        headers={'Message-ID': message_id}  # Set the Message-ID explicitly
    )

    # threading headers
    if params.get('reply_to_message_id'):
        # Get the parent message to build the References header
        parent = Message.objects.filter(id=params['reply_to_message_id']).first()
        references = []
        
        if parent:
            # First add any existing References from parent
            if parent.raw and 'References' in parent.raw:
                references.extend(parent.raw['References'].split())
            # Then add the parent's Message-ID
            references.append(params['reply_to_message_id'])
        else:
            # If parent not found, just use reply_to_message_id
            references = [params['reply_to_message_id']]
            
        email_msg.extra_headers['In-Reply-To'] = params['reply_to_message_id']
        email_msg.extra_headers['References'] = ' '.join(references)
        logger.debug(f"Added threading headers: In-Reply-To={params['reply_to_message_id']}, References={references}")

    # Always attach HTML alternative since we either have original HTML or converted text
    if html_content_for_sending:
        email_msg.attach_alternative(html_content_for_sending, "text/html")
        logger.debug("Added HTML alternative content with tracking and base64 images")

    # Attach files
    for fp in params.get('attachments', []):
        email_msg.attach_file(fp)
        logger.debug(f"Attached file: {fp}")

    # Get the message object and verify the Message-ID BEFORE sending
    msg_before_send = email_msg.message()
    msg_id_before_send = msg_before_send.get('Message-ID', '').strip()
    logger.info(f"Message-ID before send: {msg_id_before_send}")
    if msg_id_before_send != message_id:
        logger.warning(f"Message-ID changed unexpectedly before send. Original: {message_id}, Current: {msg_id_before_send}")

    # 2) send via the connection we passed in above
    try:
        email_msg.send(fail_silently=False)
        logger.info(f"Email sent successfully")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise

    # Get message bytes using the final message to maintain ID consistency
    mime_bytes = email_msg.message().as_bytes()

    # 4) save a copy in the IMAP "Sent" folder
    imap_conf = channel.config['IMAP']
    import imaplib, time
    try:
        if imap_conf['use_ssl']:
            imap_conn = imaplib.IMAP4_SSL(imap_conf['host'], imap_conf['port'])
        else:
            imap_conn = imaplib.IMAP4(imap_conf['host'], imap_conf['port'])
        
        imap_conn.login(from_addr, channel.config['EMAIL_PASSWORD'])
        timestamp = imaplib.Time2Internaldate(time.time())
        
        imap_conn.append('Sent', '\\Seen', timestamp, mime_bytes)
        logger.info("Saved copy to IMAP Sent folder")
        imap_conn.logout()
    except Exception as e:
        logger.error(f"Failed to save to IMAP Sent folder: {e}")
        raise

    # 5) delegate to save_email_message (now takes channel first)
    saved_msg = save_email_message(channel, mime_bytes, user)
    
    # Add tracking info and original content to the saved message
    saved_msg.tracking_id = tracking_id
    saved_msg.raw['original_urls'] = original_urls  # Store original URLs in raw field
    # Use the HTML with shortlinks and without tracking for DB
    if html_content:
        html_for_db = remove_tracking(revert_to_original_fa(html_content), original_urls)
        saved_msg.html = html_for_db
    saved_msg.sent = True  # Mark as sent since we successfully sent it
    saved_msg.save(update_fields=['tracking_id', 'raw', 'html', 'sent'])
    
    logger.info(f"Message saved to database with ID: {saved_msg.id} and tracking ID: {tracking_id}")
    
    return saved_msg
