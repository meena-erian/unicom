from __future__ import annotations
from typing import TYPE_CHECKING
from django.conf import settings
from django.core.mail import get_connection
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from fa2svg.converter import to_inline_png_img
from unicom.services.email.save_email_message import save_email_message
from django.apps import apps

if TYPE_CHECKING:
    from unicom.models import Channel


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

    # Build subject (fall back to “Re: <original>”)
    subject = params.get('subject')
    if not subject and params.get('reply_to_message_id'):
        from unicom.models import Message
        parent = Message.objects.filter(id=params['reply_to_message_id']).first()
        if parent:
            # count existing "Re: " prefixes, then add exactly one more
            base = parent.subject or ""
            count = 0
            while base.lower().startswith("re: "):
                count += 1
                base = base[4:]
            subject = "Re: " * (count + 1) + base
        else:
            subject = ""

    # 1) construct the EmailMultiAlternatives
    email_msg = EmailMultiAlternatives(
        subject=subject,
        body=params.get('text', ''),
        from_email=from_addr,
        to=to_addrs,
        cc=cc_addrs,
        bcc=bcc_addrs,
        connection=connection,
    )

    # threading headers
    if params.get('reply_to_message_id'):
        email_msg.extra_headers['In-Reply-To']  = params['reply_to_message_id']
        email_msg.extra_headers['References']   = params.get(
            'references', params['reply_to_message_id']
        )

    # HTML alternative
    if params.get('html'):
        email_msg.attach_alternative(to_inline_png_img(params['html']), "text/html")

    # Attach files
    for fp in params.get('attachments', []):
        email_msg.attach_file(fp)

    # 2) send via the connection we passed in above
    email_msg.send(fail_silently=False)

    # 3) grab the true, rendered MIME bytes (with real Message-ID)
    mime_bytes = email_msg.message().as_bytes()

    # 4) save a copy in the IMAP “Sent” folder
    imap_conf = channel.config['IMAP']
    import imaplib, time
    if imap_conf['use_ssl']:
        imap_conn = imaplib.IMAP4_SSL(imap_conf['host'], imap_conf['port'])
    else:
        imap_conn = imaplib.IMAP4(imap_conf['host'], imap_conf['port'])
    imap_conn.login(from_addr, channel.config['EMAIL_PASSWORD'])
    # adjust mailbox name if your server uses e.g. "Sent Items"
    imap_conn.append('Sent', '\\Seen', imaplib.Time2Internaldate(time.time()), mime_bytes)
    imap_conn.logout()

    # 5) delegate to save_email_message (now takes channel first)
    return save_email_message(channel, mime_bytes, user)

"""
from unicom.models import Message
email_messsage = Message.objects.filter(platform='Email').order_by('-timestamp').first()
email_messsage.reply_with({"html": "<h1>I hear you in H1</h1>"})
email_messsage.reply_with({"text": "I hear you in plain text"})
"""