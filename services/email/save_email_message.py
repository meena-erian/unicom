# /unicom/services/email/save_email_message.py
import re
from email import policy, message_from_bytes
from email.utils import parseaddr, parsedate_to_datetime, getaddresses
from django.utils import timezone
import logging

from django.core.files.base import ContentFile
from django.conf import settings
from django.contrib.auth.models import User
from unicom.services.email.email_tracking import remove_tracking
from django.urls import reverse
from unicom.services.get_public_origin import get_public_origin

logger = logging.getLogger(__name__)

def save_email_message(channel, raw_message_bytes: bytes, user: User = None):
    """
    Save an email into Message, creating Account, Chat, AccountChat as needed.
    `raw_message_bytes` should be the full RFC-5322 bytes you get from IMAPClient.fetch(uid, ['BODY.PEEK[]'])
    """
    from unicom.models import Message, Chat, Account, AccountChat, Channel
    platform = 'Email'

    # --- 1) parse the email -------------------
    msg = message_from_bytes(raw_message_bytes, policy=policy.default)

    # Determine if this is an outgoing message (sent by our bot)
    from_name, from_email = parseaddr(msg.get('From', ''))
    bot_email = channel.config['EMAIL_ADDRESS'].lower()
    is_outgoing = (from_email.lower() == bot_email)

    # Check if sender is blocked
    account = Account.objects.filter(platform=platform, id=from_email).first()
    if account and account.blocked:
        # For blocked accounts, we just mark as opened but don't save
        return None

    # headers
    hdr_id        = msg.get('Message-ID')            # primary key
    hdr_in_reply  = msg.get('In-Reply-To')           # parent Message-ID
    hdr_references = msg.get('References', '').split()  # all referenced messages
    hdr_subject   = msg.get('Subject', '')
    date_hdr      = msg.get('Date')

    logger.debug(f"Processing email - Message-ID: {hdr_id}, In-Reply-To: {hdr_in_reply}, References: {hdr_references}")

    # timestamp → make UTC-aware, fallback to timezone.now()
    try:
        raw_ts = parsedate_to_datetime(date_hdr)
        if raw_ts.tzinfo is None:
            raw_ts = timezone.make_aware(raw_ts, timezone.utc)
        timestamp = raw_ts
    except Exception:
        timestamp = timezone.now()

    # sender
    sender_name, sender_email = parseaddr(msg.get('From'))
    sender_name = sender_name or sender_email

    # --- recipients: To, Cc, Bcc ---
    raw_to  = msg.get_all('To', [])
    raw_cc  = msg.get_all('Cc', [])
    raw_bcc = msg.get_all('Bcc', [])

    to_list  = [email for name, email in getaddresses(raw_to)]
    cc_list  = [email for name, email in getaddresses(raw_cc)]
    bcc_list = [email for name, email in getaddresses(raw_bcc)]

    # --- Find parent message and associated chat ---
    parent_msg = None
    chat_obj = None
    
    # First try In-Reply-To
    if hdr_in_reply:
        parent_msg = Message.objects.filter(platform=platform, id=hdr_in_reply).first()
        if parent_msg:
            chat_obj = parent_msg.chat
            logger.debug(f"Found parent message {parent_msg.id} in chat {chat_obj.id} via In-Reply-To")
    
    # If no parent found, try References header
    if not parent_msg and hdr_references:
        # Try each reference in reverse order (most recent first)
        for ref in reversed(hdr_references):
            parent_msg = Message.objects.filter(platform=platform, id=ref).first()
            if parent_msg:
                chat_obj = parent_msg.chat
                logger.debug(f"Found parent message {parent_msg.id} in chat {chat_obj.id} via References")
                break
    
    # If still no chat found, create new one
    if not chat_obj:
        chat_obj, created = Chat.objects.get_or_create(
            platform=platform,
            id=hdr_id,  # Use current message ID as chat ID for new threads
            defaults={'channel': channel, 'is_private': True, 'name': hdr_subject}
        )
        if created:
            logger.debug(f"Created new chat {chat_obj.id} for message {hdr_id}")

    # --- ensure Account exists ---
    account_obj, _ = Account.objects.get_or_create(
        platform=platform,
        id=sender_email,
        defaults={'channel': channel, 'name': sender_name, 'is_bot': is_outgoing, 'raw': dict(msg.items())}
    )
    AccountChat.objects.get_or_create(account=account_obj, chat=chat_obj)

    # --- bodies ---
    text_parts = []
    html_parts = []
    for part in msg.walk():
        if part.get_content_disposition() == 'attachment':
            continue
        ctype   = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or 'utf-8'
        content = payload.decode(charset, errors='replace')
        if ctype == 'text/plain':
            text_parts.append(content)
        elif ctype == 'text/html':
            html_parts.append(content)

    body_text = "\n".join(text_parts).strip()
    body_html = "\n".join(html_parts).strip() or None

    # If this is an outgoing message with tracking, remove tracking elements
    if is_outgoing and body_html:
        original_urls = []
        if parent_msg and parent_msg.raw.get('original_urls'):
            original_urls = parent_msg.raw['original_urls']
        body_html = remove_tracking(body_html, original_urls)

    # Extract plain text from HTML if no text version available
    if not body_text and body_html:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(body_html, 'html.parser')
        body_text = soup.get_text()

    # --- extract and save inline base64 images, build HTML with shortlinks ---
    inline_image_pks = []
    if body_html:
        from bs4 import BeautifulSoup
        import base64
        import mimetypes
        from unicom.models import EmailInlineImage
        soup = BeautifulSoup(body_html, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src.startswith('data:image/') and ';base64,' in src:
                header, b64data = src.split(';base64,', 1)
                mime = header.split(':')[1]
                ext = mimetypes.guess_extension(mime) or '.png'
                data = base64.b64decode(b64data)
                content_id = img.get('cid') or None
                image_obj = EmailInlineImage.objects.create(
                    email_message=None,
                    content_id=content_id
                )
                fname = f'inline_{image_obj.pk}{ext}'
                image_obj.file.save(fname, ContentFile(data), save=True)
                
                # Generate full public URL
                short_id = image_obj.get_short_id()
                path = reverse('inline_image', kwargs={'shortid': short_id})
                public_url = f"{get_public_origin().strip('/')}{path}"
                img['src'] = public_url
                inline_image_pks.append(image_obj.pk)
        body_html = str(soup)

    # --- save into your Message model ---
    msg_obj, created = Message.objects.get_or_create(
        platform=platform,
        chat=chat_obj,
        id=hdr_id,
        defaults={
            'sender': account_obj,
            'sender_name': sender_name,
            'is_outgoing': is_outgoing,
            'user': user,
            'text': body_text,
            'html': body_html,
            'subject': hdr_subject,
            'timestamp': timestamp,
            'reply_to_message': parent_msg,
            'raw': dict(msg.items()),
            'to': to_list,
            'cc': cc_list,
            'bcc': bcc_list,
            'media_type': 'html',
            'channel': channel
        }
    )

    # If message already existed, update its HTML if it changed
    if not created and msg_obj.html != body_html:
        msg_obj.html = body_html
        msg_obj.save(update_fields=['html'])

    # Associate any newly created inline images with the message
    if inline_image_pks:
        from unicom.models import EmailInlineImage
        EmailInlineImage.objects.filter(pk__in=inline_image_pks).update(email_message=msg_obj)

    if not created:
        logger.debug(f"Message {msg_obj.id} already exists in chat {chat_obj.id}")
        return msg_obj

    logger.debug(f"Created new message {msg_obj.id} in chat {chat_obj.id}")

    # handle first attachment only
    attachments = [part for part in msg.iter_attachments() if part.get_content_disposition() == 'attachment' and not part.get('Content-ID')]
    if attachments:
        media_part = attachments[0]
        data = media_part.get_payload(decode=True)
        if data:
            fname = media_part.get_filename() or 'attachment'
            cf = ContentFile(data)
            msg_obj.media.save(fname, cf, save=True)
            ctype = media_part.get_content_type()
            if ctype.startswith('image/'):
                msg_obj.media_type = 'image'
            elif ctype.startswith('audio/'):
                msg_obj.media_type = 'audio'
            else:
                msg_obj.media_type = 'file'
            msg_obj.save(update_fields=['media', 'media_type'])

    return msg_obj