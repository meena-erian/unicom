from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from fa2svg.converter import to_inline_png_img
from unicom.services.email.save_email_message import save_email_message


def send_email_message(params: dict, user: User=None):
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

    from_addr = settings.EMAIL_HOST_USER
    to_addrs  = [params['chat_id']]
    cc_addrs  = params.get('cc', [])
    bcc_addrs = params.get('bcc', [])

    # Build subject (fall back to “Re: <original>”)
    subject = params.get('subject')
    if not subject and params.get('reply_to_message_id'):
        from unicom.models import Message
        parent = Message.objects.filter(id=params['reply_to_message_id']).first()
        subject = f"Re: {parent.subject}" if parent else ""

    # 1) construct the EmailMultiAlternatives
    email_msg = EmailMultiAlternatives(
        subject=subject,
        body=params.get('text', ''),
        from_email=from_addr,
        to=to_addrs,
        cc=cc_addrs,
        bcc=bcc_addrs,
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

    # 2) send
    email_msg.send()

    # 3) grab the true, rendered MIME bytes (with real Message-ID)
    mime_bytes = email_msg.message().as_bytes()

    # 4) delegate to the same save_email_message
    return save_email_message(mime_bytes, user)
