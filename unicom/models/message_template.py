from django.db import models
from django.utils.translation import gettext_lazy as _

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