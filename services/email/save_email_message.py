import re
from email import policy, message_from_bytes
from email.utils import parseaddr, parsedate_to_datetime, getaddresses
from django.utils import timezone

from django.core.files.base import ContentFile
from django.conf import settings
from django.contrib.auth.models import User

from unicom.models import Message, Chat, Account, AccountChat

def save_email_message(raw_message_bytes: bytes, user: User=None):
    """
    Save an email into Message, creating Account, Chat, AccountChat as needed.
    `raw_message_bytes` should be the full RFC-5322 bytes you get from IMAPClient.fetch(uid, ['BODY.PEEK[]'])
    """
    platform = 'Email'

    # --- 1) parse the email -------------------
    msg = message_from_bytes(raw_message_bytes, policy=policy.default)

    # Determine if this is an outgoing message (sent by our bot)
    from_name, from_email = parseaddr(msg.get('From', ''))
    bot_email = settings.EMAIL_HOST_USER.lower()
    outgoing = (from_email.lower() == bot_email)

    # headers
    hdr_id        = msg.get('Message-ID')            # primary key
    hdr_in_reply  = msg.get('In-Reply-To')           # parent Message-ID
    hdr_subject   = msg.get('Subject', '')
    date_hdr      = msg.get('Date')

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

    # parseaddresses → list of (name, email); we only need email
    to_list  = [email for name, email in getaddresses(raw_to)]
    cc_list  = [email for name, email in getaddresses(raw_cc)]
    bcc_list = [email for name, email in getaddresses(raw_bcc)]

    # --- ensure Chat & Account exist ---
    if hdr_in_reply:
        parent_msg = Message.objects.filter(platform=platform, id=hdr_in_reply).first()
        if parent_msg:
            chat_obj = Chat.objects.get(platform=platform, id=parent_msg.chat_id)
        else:
            chat_obj, _ = Chat.objects.get_or_create(
                platform=platform,
                id=hdr_id,
                defaults={'is_private': True, 'name': hdr_subject}
            )
    else:
        chat_obj, _ = Chat.objects.get_or_create(
            platform=platform,
            id=hdr_id,
            defaults={'is_private': True, 'name': hdr_subject}
        )

    account_obj, _ = Account.objects.get_or_create(
        platform=platform,
        id=sender_email,
        defaults={'name': sender_name, 'is_bot': outgoing, 'raw': dict(msg.items())}
    )
    AccountChat.objects.get_or_create(account=account_obj, chat=chat_obj)

    # --- threading ---
    parent = None
    if hdr_in_reply:
        parent = Message.objects.filter(platform=platform, id=hdr_in_reply).first()

    # --- bodies ---
    text_parts = []
    html_parts = []
    for part in msg.walk():
        # skip attachments here
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

    # fallback: strip tags if no plain text
    if not body_text and body_html:
        body_text = re.sub(r'<[^>]+>', '', body_html)

    # --- 7) save into your Message model ---
    msg_obj, created = Message.objects.get_or_create(
        platform   = platform,
        chat_id    = chat_obj.id,
        id         = hdr_id,
        defaults   = {
            'sender_id'        : account_obj.id,
            'sender_name'      : sender_name,
            'is_bot'           : outgoing,
            'user'             : user,
            'text'             : body_text,
            'html'             : body_html,
            'subject'          : hdr_subject,
            'timestamp'        : timestamp,
            'reply_to_message' : parent,
            'raw'              : dict(msg.items()),
            'to'               : to_list,
            'cc'               : cc_list,
            'bcc'              : bcc_list,
            'media_type'       : 'html',
        }
    )

    if not created:
        # already seen this Message-ID
        return msg_obj

    attachments = []
    for part in msg.iter_attachments():
        disp = part.get_content_disposition()  # ‘inline’ or ‘attachment’
        cid  = part.get('Content-ID')          # e.g. '<logo123@…>'
        if disp != 'attachment':
            continue
        if cid:
            # probably an inline image; skip it
            continue
        attachments.append(part)
        
        # break # only save the first attachment for now
    if attachments:
        media_part = attachments[0]
        data = media_part.get_payload(decode=True)
        if data:
            fname = media_part.get_filename() or 'attachment'
            cf = ContentFile(data)
            msg_obj.media.save(fname, cf, save=True)

            ctype = media_part.get_content_type()  # e.g. 'image/png', 'application/pdf', 'audio/mpeg'
            if ctype.startswith('image/'):
                msg_obj.media_type = 'image'
            elif ctype.startswith('audio/'):
                msg_obj.media_type = 'audio'
            else:
                msg_obj.media_type = 'file'  # or extend TYPE_CHOICES with 'file'
            msg_obj.save(update_fields=['media', 'media_type'])
            # then save msg_obj.media from media_part.get_payload(decode=True)
    msg_obj.save()
    return msg_obj
