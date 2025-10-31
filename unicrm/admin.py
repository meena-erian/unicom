import json

from django import forms
from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from django_ace import AceWidget

from . import models


class TemplateVariableForm(forms.ModelForm):
    class Meta:
        model = models.TemplateVariable
        fields = '__all__'
        widgets = {
            'code': AceWidget(
                mode='python',
                theme='github',
                width='100%',
                height='260px',
                fontsize='12px',
                showprintmargin=False,
            ),
        }


class SegmentForm(forms.ModelForm):
    class Meta:
        model = models.Segment
        fields = '__all__'
        widgets = {
            'code': AceWidget(
                mode='python',
                theme='github',
                width='100%',
                height='260px',
                fontsize='12px',
                showprintmargin=False,
            ),
        }


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'domain', 'website', 'created_at')
    search_fields = ('name', 'domain')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(models.Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'company', 'owner', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('company',)
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('company', 'owner')


@admin.register(models.MailingList)
class MailingListAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(models.Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('contact', 'mailing_list', 'subscribed_at', 'unsubscribed_at')
    list_filter = ('mailing_list',)
    search_fields = ('contact__email', 'contact__first_name', 'contact__last_name')
    autocomplete_fields = ('contact', 'mailing_list')
    readonly_fields = ('created_at', 'updated_at', 'subscribed_at')


@admin.register(models.Segment)
class SegmentAdmin(admin.ModelAdmin):
    form = SegmentForm
    list_display = ('name', 'contact_count', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'contact_count', 'contact_sample')

    fieldsets = (
        (None, {'fields': ('name', 'description')}),
        (_('Filter code'), {'fields': ('code',)}),
        (_('Preview'), {'fields': ('contact_count', 'contact_sample')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )

    def contact_count(self, obj):
        if not obj.pk:
            return _('Save to preview contacts')
        try:
            return obj.apply().count()
        except Exception as exc:  # pragma: no cover - defensive
            return format_html('<span style="color:red;">Error: {}</span>', exc)

    contact_count.short_description = _('Matching contacts')

    def contact_sample(self, obj):
        if not obj.pk:
            return _('Save to preview contacts')
        contacts = obj.sample_contacts(limit=10)
        if not contacts:
            return _('No contacts match this segment yet.')
        rows = [(str(contact), contact.email) for contact in contacts]
        return format_html(
            '<ul style="margin:0;">{}</ul>',
            format_html_join('', '<li><strong>{}</strong> &lt;{}&gt;</li>', rows)
        )

    contact_sample.short_description = _('Sample contacts')


@admin.register(models.TemplateVariable)
class TemplateVariableAdmin(admin.ModelAdmin):
    form = TemplateVariableForm
    list_display = ('key', 'label', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('key', 'label')
    readonly_fields = ('created_at', 'updated_at', 'sample_preview')

    fieldsets = (
        (None, {'fields': ('key', 'label', 'description', 'is_active')}),
        (_('Code'), {'fields': ('code',)}),
        (_('Preview'), {'fields': ('sample_preview',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )

    def sample_preview(self, obj):
        if not obj.pk:
            return _('Save to preview sample output')
        values = obj.sample_values(limit=3)
        return format_html(
            '<ul style="margin:0;">{}</ul>',
            format_html_join('', '<li>{}</li>', ((value,) for value in values))
        )

    sample_preview.short_description = _('Sample output')


@admin.register(models.Communication)
class CommunicationAdmin(admin.ModelAdmin):
    list_display = ('template', 'segment', 'status', 'scheduled_for', 'created_at')
    list_filter = ('status',)
    search_fields = ('template__title', 'segment__name')
    autocomplete_fields = ('segment', 'template', 'initiated_by')
    readonly_fields = ('created_at', 'updated_at', 'status_summary_pretty')

    fieldsets = (
        (None, {'fields': ('template', 'segment', 'initiated_by', 'status', 'scheduled_for')}),
        (_('Status summary'), {'fields': ('status_summary_pretty',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )

    def status_summary_pretty(self, obj):
        summary = json.dumps(obj.status_summary or {}, indent=2, default=str)
        return format_html('<pre style="white-space:pre-wrap;">{}</pre>', summary)

    status_summary_pretty.short_description = _('Aggregated status')


@admin.register(models.CommunicationMessage)
class CommunicationMessageAdmin(admin.ModelAdmin):
    list_display = ('communication', 'contact', 'message', 'derived_status', 'created_at')
    search_fields = ('communication__template__title', 'contact__email', 'message__id')
    autocomplete_fields = ('communication', 'contact', 'message')
    readonly_fields = ('created_at', 'updated_at', 'derived_status')

    def derived_status(self, obj):
        return obj.message_status()

    derived_status.short_description = _('Message status')
