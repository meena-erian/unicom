import base64
import mimetypes
import re
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.urls import reverse
from unicom.models import EmailInlineImage
from unicom.services.get_public_origin import get_public_origin
from typing import Optional
import string

def base62_encode(n: int) -> str:
    chars = string.digits + string.ascii_letters
    s = ''
    if n == 0:
        return chars[0]
    while n > 0:
        n, r = divmod(n, 62)
        s = chars[r] + s
    return s

def base62_decode(s: str) -> int:
    chars = string.digits + string.ascii_letters
    n = 0
    for c in s:
        n = n * 62 + chars.index(c)
    return n

def html_base64_images_to_shortlinks(html: str) -> str:
    """
    Converts base64 images in HTML to shortlinks, saves them as EmailInlineImage (email_message=None),
    and replaces <img src="data:image/..."> with <img src="shortlink">.
    Returns the modified HTML.
    """
    if not html:
        return html
    soup = BeautifulSoup(html, 'html.parser')
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
            # Generate shortlink
            short_id = image_obj.get_short_id()
            path = reverse('inline_image', kwargs={'shortid': short_id})
            public_url = f"{get_public_origin().strip('/')}{path}"
            img['src'] = public_url
    return str(soup)

def html_shortlinks_to_base64_images(html: str) -> str:
    """
    Converts <img src="shortlink"> in HTML to <img src="data:image/..."> by looking up EmailInlineImage.
    Returns the modified HTML.
    """
    if not html:
        return html
    soup = BeautifulSoup(html, 'html.parser')
    for img_tag in soup.find_all('img'):
        src = img_tag.get('src', '')
        # Extract short id from src (e.g., /i/abc123 or full URL)
        m = re.search(r'/i/([A-Za-z0-9]+)', src)
        if m:
            short_id = m.group(1)
            try:
                pk = base62_decode(short_id)
                image_obj = EmailInlineImage.objects.get(pk=pk)
                # Read file and encode as base64
                data = image_obj.file.read()
                image_obj.file.seek(0)
                mime = 'image/png'  # Default
                if hasattr(image_obj.file, 'file') and hasattr(image_obj.file.file, 'content_type'):
                    mime = image_obj.file.file.content_type
                elif image_obj.file.name:
                    mime = mimetypes.guess_type(image_obj.file.name)[0] or 'image/png'
                b64 = base64.b64encode(data).decode('ascii')
                img_tag['src'] = f'data:{mime};base64,{b64}'
            except Exception:
                continue
    return str(soup) 