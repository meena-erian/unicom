from __future__ import annotations
from typing import TYPE_CHECKING
from django.conf import settings
from django.core.mail import get_connection
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from fa2svg.converter import to_inline_png_img
from unicom.services.email.save_email_message import save_email_message
from unicom.services.email.email_tracking import prepare_email_for_tracking
from django.apps import apps
import logging
from email.utils import make_msgid
import uuid
import html

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
    params keys:
      - chat_id              : recipient email address (string)
      - reply_to_message_id  : original Message-ID header (string)
      - text                 : plain-text body
      - html                 : (optional) HTML body
      - cc, bcc              : lists of email strings
      - attachments          : list of local file paths
      - subject              : optional override for subject
    """
    Message = apps.get_model('unicom', 'Message')
    from_addr = channel.config['EMAIL_ADDRESS']
    smtp_conf = channel.config['SMTP']
    connection = get_connection(
        host=smtp_conf['host'],
        port=smtp_conf['port'],
        username=from_addr,
        password=channel.config['EMAIL_PASSWORD'],
        use_ssl=smtp_conf['use_ssl'],
    )
    to_addrs  = [params['chat_id']]
    cc_addrs  = params.get('cc', [])
    bcc_addrs = params.get('bcc', [])

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
    message_id = make_msgid(domain="insightifyr.portacode.com")
    tracking_id = uuid.uuid4()
    logger.info(f"Generated Message-ID: {message_id}, Tracking-ID: {tracking_id}")

    # Handle HTML content
    text_content = params.get('text', '')
    html_content = params.get('html')
    
    # If HTML is not provided but text is, convert text to HTML
    if not html_content and text_content:
        html_content = convert_text_to_html(text_content)
        logger.debug("Converted plain text to HTML")

    # Store original HTML content before adding tracking
    original_html = html_content
    if original_html:
        original_html = to_inline_png_img(original_html)  # Convert FontAwesome to inline images

    # Prepare HTML content with tracking
    original_urls = []
    if html_content:
        html_content, original_urls = prepare_email_for_tracking(html_content, tracking_id)
        logger.debug("Added tracking elements to HTML content")

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
    if html_content:
        email_msg.attach_alternative(html_content, "text/html")
        logger.debug("Added HTML alternative content with tracking")

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
    saved_msg.html = original_html  # Store the original HTML without tracking
    saved_msg.sent = True  # Mark as sent since we successfully sent it
    saved_msg.save(update_fields=['tracking_id', 'raw', 'html', 'sent'])
    
    logger.info(f"Message saved to database with ID: {saved_msg.id} and tracking ID: {tracking_id}")
    
    return saved_msg

"""
from unicom.models import Message
email_messsage = Message.objects.filter(platform='Email').order_by('timestamp').first()
email_messsage.reply_with({"html": "<h1>First outgoing email</h1>"})
email_messsage.reply_with({"text": "I hear you in plain text"})
"""