from django.contrib import admin
from django import forms
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from ..models import MessageTemplate
from ..models.message_template import MessageTemplateInlineImage

class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_at', 'updated_at')
    list_filter = ('category', 'channels')
    search_fields = ('title', 'description', 'content')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('channels',)
    
    fieldsets = (
        (None, {
            'fields': ('title', 'category')
        }),
        (_('Template Content'), {
            'fields': ('description', 'content'),
            'classes': ('tinymce-content',),
        }),
        (_('Availability'), {
            'fields': ('channels',),
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Only include the local tinymce_init.js, not the CDN script
        form.Media = type('Media', (), {
            'css': {'all': ('admin/css/forms.css',)},
            'js': (
                'unicom/js/tinymce_init.js',
            )
        })
        return form

    def render_change_form(self, request, context, *args, **kwargs):
        context['tinymce_api_key'] = settings.UNICOM_TINYMCE_API_KEY
        return super().render_change_form(request, context, *args, **kwargs)

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'content':
            kwargs['widget'] = forms.Textarea(attrs={
                'class': 'tinymce',
                'data-tinymce': 'true'
            })
        return super().formfield_for_dbfield(db_field, **kwargs)

class MessageTemplateInlineImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'template', 'created_at', 'serving_link')
    readonly_fields = ('serving_link',)

    def serving_link(self, obj):
        if not obj.pk:
            return "(save to get link)"
        shortid = obj.get_short_id()
        path = self._get_reverse_path(shortid)
        url = self._get_public_url(path)
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)
    serving_link.short_description = "Serving Link"

    def _get_reverse_path(self, shortid):
        from django.urls import reverse
        return reverse('template_inline_image', kwargs={'shortid': shortid})

    def _get_public_url(self, path):
        from unicom.services.get_public_origin import get_public_origin
        return f"{get_public_origin().rstrip('/')}" + path 