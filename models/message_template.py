from django.db import models
from django.utils.translation import gettext_lazy as _
import re
from bs4 import BeautifulSoup
import base64
from django.core.files.base import ContentFile
from django.urls import reverse
from unicom.services.get_public_origin import get_public_origin

class MessageTemplate(models.Model):
    """Model for storing reusable message templates."""
    
    title = models.CharField(
        _('Title'),
        max_length=200,
        help_text=_('Template title/name for easy identification')
    )
    
    description = models.TextField(
        _('Description'),
        blank=True,
        help_text=_('Optional description of what this template is used for')
    )
    
    content = models.TextField(
        _('Content'),
        help_text=_('The HTML content of the template')
    )
    
    category = models.CharField(
        _('Category'),
        max_length=100,
        blank=True,
        help_text=_('Optional category for organizing templates')
    )

    channels = models.ManyToManyField(
        'Channel',
        verbose_name=_('Channels'),
        blank=True,
        help_text=_('Channels where this template can be used')
    )
    
    created_at = models.DateTimeField(
        _('Created at'),
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        _('Updated at'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('Message Template')
        verbose_name_plural = _('Message Templates')
        ordering = ['category', 'title']

    def __str__(self):
        return self.title 

    @property
    def html_with_base64_images(self):
        """
        Returns the HTML content with all inline image shortlinks replaced by their original base64 data, if available.
        """
        if not self.content:
            return self.content
        soup = BeautifulSoup(self.content, 'html.parser')
        images = {img.get_short_id(): img for img in getattr(self, 'inline_images', [])}
        for img_tag in soup.find_all('img'):
            src = img_tag.get('src', '')
            m = re.search(r'/i/([A-Za-z0-9]+)', src)
            if m:
                short_id = m.group(1)
                image_obj = images.get(short_id)
                if image_obj:
                    data = image_obj.file.read()
                    image_obj.file.seek(0)
                    mime = 'image/png'
                    if hasattr(image_obj.file, 'file') and hasattr(image_obj.file.file, 'content_type'):
                        mime = image_obj.file.file.content_type
                    elif image_obj.file.name:
                        import mimetypes
                        mime = mimetypes.guess_type(image_obj.file.name)[0] or 'image/png'
                    b64 = base64.b64encode(data).decode('ascii')
                    img_tag['src'] = f'data:{mime};base64,{b64}'
        return str(soup)

    def save(self, *args, **kwargs):
        # First, save the template to ensure it has a PK
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Only process if content is present
        if self.content:
            from bs4 import BeautifulSoup
            import base64
            import mimetypes
            from django.core.files.base import ContentFile
            from django.urls import reverse
            from unicom.services.get_public_origin import get_public_origin
            soup = BeautifulSoup(self.content, 'html.parser')
            changed = False
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if src.startswith('data:image/') and ';base64,' in src:
                    header, b64data = src.split(';base64,', 1)
                    mime = header.split(':')[1]
                    ext = mimetypes.guess_extension(mime) or '.png'
                    data = base64.b64decode(b64data)
                    content_id = img.get('cid') or None
                    image_obj = MessageTemplateInlineImage.objects.create(
                        template=self,
                        content_id=content_id
                    )
                    fname = f'inline_{image_obj.pk}{ext}'
                    image_obj.file.save(fname, ContentFile(data), save=True)
                    short_id = image_obj.get_short_id()
                    path = reverse('template_inline_image', kwargs={'shortid': short_id})
                    public_url = f"{get_public_origin().rstrip('/')}{path}"
                    img['src'] = public_url
                    changed = True
            if changed:
                self.content = str(soup)
                # Save again to update content with shortlinks
                super().save(update_fields=['content'])

class MessageTemplateInlineImage(models.Model):
    file = models.FileField(upload_to='message_template_inline_images/')
    template = models.ForeignKey(MessageTemplate, on_delete=models.CASCADE, related_name='inline_images')
    created_at = models.DateTimeField(auto_now_add=True)
    content_id = models.CharField(max_length=255, blank=True, null=True, help_text='Content-ID for cid: references in HTML')

    def get_short_id(self):
        import string
        chars = string.digits + string.ascii_letters
        n = self.pk
        s = ''
        if n == 0:
            return chars[0]
        while n > 0:
            n, r = divmod(n, 62)
            s = chars[r] + s
        return s 