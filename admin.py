from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _
from unicom.models import Message, Update, Chat, Account, AccountChat, Channel
from django.utils.html import format_html
from unicom.views.chat_history_view import chat_history_view
from unicom.views.compose_view import compose_view
from django.urls import path, reverse
from django_ace import AceWidget
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta
from unicom.models import (
    Member,
    MemberGroup,
    RequestCategory,
    Request,
    MessageTemplate,
    DraftMessage,
    EmailInlineImage
)
from django import forms
from django.conf import settings
from django.utils.safestring import mark_safe
from unicom.services.get_public_origin import get_public_origin
from unicom.models.message_template import MessageTemplateInlineImage


class ArchiveStatusFilter(SimpleListFilter):
    title = _('Archive Status')
    parameter_name = 'archive_status'
    default_value = 'unarchived'

    def lookups(self, request, model_admin):
        return (
            ('unarchived', _('Unarchived')),
            ('archived', _('Archived')),
            ('all', _('All Chats')),
        )

    def queryset(self, request, queryset):
        value = self.value() or self.default_value
        if value == 'unarchived':
            return queryset.filter(is_archived=False)
        if value == 'archived':
            return queryset.filter(is_archived=True)
        # if value == 'all':
        return queryset

    def choices(self, changelist):
        value = self.value() or self.default_value
        for lookup, title in self.lookup_choices:
            yield {
                'selected': value == str(lookup),
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }


class LastMessageTypeFilter(SimpleListFilter):
    title = _('Last Message Type')
    parameter_name = 'last_message_type'

    def lookups(self, request, model_admin):
        return (
            ('incoming', _('Needs Response')),
            ('outgoing', _('We Responded Last')),
            ('none', _('No Messages')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'incoming':
            return queryset.filter(last_message__is_outgoing=False)
        if self.value() == 'outgoing':
            return queryset.filter(last_message__is_outgoing=True)
        if self.value() == 'none':
            return queryset.filter(last_message__isnull=True)


class LastMessageTimeFilter(SimpleListFilter):
    title = _('Last Activity')
    parameter_name = 'last_activity'

    def lookups(self, request, model_admin):
        return (
            ('1h', _('Within 1 hour')),
            ('24h', _('Within 24 hours')),
            ('7d', _('Within 7 days')),
            ('30d', _('Within 30 days')),
            ('old', _('Older than 30 days')),
            ('none', _('No activity')),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == '1h':
            return queryset.filter(last_message__timestamp__gte=now - timedelta(hours=1))
        if self.value() == '24h':
            return queryset.filter(last_message__timestamp__gte=now - timedelta(days=1))
        if self.value() == '7d':
            return queryset.filter(last_message__timestamp__gte=now - timedelta(days=7))
        if self.value() == '30d':
            return queryset.filter(last_message__timestamp__gte=now - timedelta(days=30))
        if self.value() == 'old':
            return queryset.filter(last_message__timestamp__lt=now - timedelta(days=30))
        if self.value() == 'none':
            return queryset.filter(last_message__isnull=True)


class MessageHistoryFilter(SimpleListFilter):
    title = _('Message History')
    parameter_name = 'message_history'

    def lookups(self, request, model_admin):
        return (
            ('has_both', _('Has both incoming & outgoing')),
            ('only_incoming', _('Only incoming messages')),
            ('only_outgoing', _('Only outgoing messages')),
            ('empty', _('No messages')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'has_both':
            return queryset.filter(
                first_incoming_message__isnull=False,
                first_outgoing_message__isnull=False
            )
        if self.value() == 'only_incoming':
            return queryset.filter(
                first_incoming_message__isnull=False,
                first_outgoing_message__isnull=True
            )
        if self.value() == 'only_outgoing':
            return queryset.filter(
                first_incoming_message__isnull=True,
                first_outgoing_message__isnull=False
            )
        if self.value() == 'empty':
            return queryset.filter(
                first_message__isnull=True
            )


class ChatAdmin(admin.ModelAdmin):
    list_filter = (
        LastMessageTypeFilter,
        LastMessageTimeFilter,
        MessageHistoryFilter,
        ArchiveStatusFilter,
        'platform',
        'is_private',
        'channel',
    )
    list_display = ('chat_info',)
    search_fields = ('id', 'name', 'messages__text', 'messages__sender__name')
    actions = ['archive_chats', 'unarchive_chats']

    class Media:
        css = {
            'all': (
                'admin/css/chat_list.css',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css',
            )
        }

    def get_queryset(self, request):
        # The filtering logic is now handled by the ArchiveStatusFilter.
        return super().get_queryset(request).order_by('-last_message__timestamp')

    def archive_chats(self, request, queryset):
        updated = queryset.update(is_archived=True)
        self.message_user(request, f'{updated} chat(s) have been archived.')
    archive_chats.short_description = 'Archive selected chats'

    def unarchive_chats(self, request, queryset):
        updated = queryset.update(is_archived=False)
        self.message_user(request, f'{updated} chat(s) have been unarchived.')
    unarchive_chats.short_description = 'Unarchive selected chats'

    def chat_info(self, obj):
        name = obj.name or obj.id
        last_message = obj.last_message
        last_message_text = last_message.text[:100] + '...' if last_message and last_message.text and len(last_message.text) > 100 else (last_message.text if last_message else 'No messages')
        
        # Determine message status indicators
        has_incoming = obj.first_incoming_message is not None
        has_outgoing = obj.first_outgoing_message is not None
        is_last_incoming = last_message and last_message.is_outgoing is False
        
        # Create status icons HTML
        status_icons = format_html(
            '<span class="chat-status-icons">{}{}{}</span>',
            format_html('<i class="fas fa-inbox" title="Has incoming messages"></i>') if has_incoming else '',
            format_html('<i class="fas fa-paper-plane" title="Has outgoing messages"></i>') if has_outgoing else '',
            format_html('<i class="fas fa-archive" title="Archived"></i>') if obj.is_archived else ''
        )
        
        # Create last message icon
        last_message_icon = ''
        if last_message:
            if is_last_incoming:
                last_message_icon = format_html('<i class="fas fa-reply pending-response" title="Pending response"></i>')
            else:
                last_message_icon = format_html('<i class="fas fa-check" title="Last message was outgoing"></i>')
        
        return format_html('''
            <a href="{}" class="chat-info-container{}">
                <div class="chat-header">
                    <span class="chat-name">{}</span>
                    {}
                </div>
                <div class="chat-message">
                    <span class="message-status-icon">{}</span>
                    <span class="message-text">{}</span>
                </div>
                <div class="chat-footer">
                    <span class="chat-channel">{}</span>
                    <span class="chat-time">{}</span>
                </div>
            </a>
            <style>
                .chat-info-container {{
                    display: block;
                    padding: 10px;
                    text-decoration: none;
                    color: var(--body-fg);
                    border-radius: 4px;
                    transition: background-color 0.2s;
                }}
                .chat-info-container:hover {{
                    background-color: var(--darkened-bg);
                }}
                .chat-info-container.archived {{
                    opacity: 0.7;
                }}
                .chat-header {{
                    margin-bottom: 5px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                .chat-name {{
                    font-weight: bold;
                    font-size: 1.1em;
                    color: var(--link-fg);
                }}
                .chat-status-icons {{
                    display: flex;
                    gap: 8px;
                    font-size: 0.8em;
                    color: var(--body-quiet-color);
                }}
                .chat-status-icons i {{
                    opacity: 0.7;
                }}
                .chat-message {{
                    color: var(--body-fg);
                    margin-bottom: 5px;
                    font-size: 0.9em;
                    opacity: 0.9;
                    display: flex;
                    align-items: flex-start;
                    gap: 8px;
                }}
                .message-status-icon {{
                    flex-shrink: 0;
                    margin-top: 3px;
                }}
                .message-status-icon .pending-response {{
                    color: #e74c3c;
                }}
                .message-text {{
                    flex-grow: 1;
                }}
                .chat-footer {{
                    display: flex;
                    justify-content: space-between;
                    font-size: 0.8em;
                    color: var(--body-quiet-color);
                }}
                .chat-channel {{
                    background-color: var(--selected-row);
                    padding: 2px 6px;
                    border-radius: 3px;
                }}
                .chat-time {{
                    color: var(--body-quiet-color);
                }}
            </style>
        ''',
        self.url_for_chat(obj.id),
        ' archived' if obj.is_archived else '',
        name,
        status_icons,
        last_message_icon,
        last_message_text,
        obj.channel,
        last_message.timestamp.strftime('%Y-%m-%d %H:%M') if last_message else 'Never'
        )
    chat_info.short_description = 'Chats'
    chat_info.admin_order_field = '-last_message__timestamp'

    def url_for_chat(self, id):
        return f"{id}/messages/"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:chat_id>/messages/', self.admin_site.admin_view(chat_history_view), name='chat-detail'),
            path('compose/', self.admin_site.admin_view(compose_view), name='chat-compose'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_add_button'] = False  # Hide the default "Add" button
        return super().changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, request):
        return False  # Disable the default add form

    def get_changelist_template(self, request):
        return "admin/unicom/chat/change_list.html"


class AccountChatAdmin(admin.ModelAdmin):
    list_filter = ('account__platform', )
    search_fields = ('account__name', 'chat__name') 


class AccountAdmin(admin.ModelAdmin):
    list_filter = ('platform', )
    search_fields = ('name', )

class ChannelAdmin(admin.ModelAdmin):
    list_filter = ('platform', )
    search_fields = ('name', )
    list_display = ('id', 'name', 'platform', 'active', 'confirmed_webhook_url', 'error')
    
    formfield_overrides = {
        models.JSONField: {'widget': AceWidget(mode='json', theme='twilight', width="100%", height="300px")},
    }

    class Media:
        js = ('unicom/js/channel_config.js',)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['active', 'confirmed_webhook_url', 'error']
        return super().get_readonly_fields(request, obj)

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'group_list', 'created_at')
    list_filter = ('groups', 'created_at')
    search_fields = ('name', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('allowed_categories',)
    
    def group_list(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])
    group_list.short_description = "Groups"


@admin.register(MemberGroup)
class MemberGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'member_count', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('members',)

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = "Number of Members"


@admin.register(RequestCategory)
class RequestCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'sequence', 'is_active', 'is_public')
    list_filter = ('is_active', 'is_public', 'parent')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('allowed_channels', 'authorized_members', 'authorized_groups')
    
    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'processing_function':
            kwargs['widget'] = AceWidget(
                mode='python',
                theme='twilight',
                width="100%",
                height="300px"
            )
        return super().formfield_for_dbfield(db_field, **kwargs)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Prevent a category from being its own parent
        if obj:
            form.base_fields['parent'].queryset = RequestCategory.objects.exclude(pk=obj.pk)
        
        # Set template code as initial value for new categories
        if not obj and 'processing_function' in form.base_fields:
            form.base_fields['processing_function'].initial = obj.get_template_code() if obj else RequestCategory().get_template_code()
        
        return form

    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }
        js = ('admin/js/jquery.init.js', 'admin/js/core.js',)


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'member_link', 'category', 'channel', 'created_at')
    list_display_links = ('__str__',)
    list_filter = (
        'status',
        'channel',
        'category',
        ('member', admin.RelatedOnlyFieldListFilter),
        ('created_at', admin.DateFieldListFilter),
    )
    search_fields = (
        'display_text',
        'message__text',
        'email',
        'phone',
        'member__name',
        'member__email',
        'member__phone',
        'metadata',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'pending_at',
        'identifying_at',
        'categorizing_at',
        'queued_at',
        'processing_at',
        'completed_at',
        'failed_at',
        'error',
    )
    raw_id_fields = ('message', 'account', 'member', 'category')
    date_hierarchy = 'created_at'

    def member_link(self, obj):
        if obj.member:
            url = f"/admin/unicom/member/{obj.member.id}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.member.name)
        return "-"
    member_link.short_description = "Member"

    fieldsets = (
        ('Message', {
            'fields': ('message', 'display_text')
        }),
        ('Basic Information', {
            'fields': ('status', 'error', 'account', 'channel', 'member')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone')
        }),
        ('Categorization', {
            'fields': ('category',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'pending_at',
                'identifying_at',
                'categorizing_at',
                'queued_at',
                'processing_at',
                'completed_at',
                'failed_at',
            ),
            'classes': ('collapse',)
        }),
    )

@admin.register(MessageTemplate)
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

class DraftScheduleFilter(SimpleListFilter):
    title = _('Schedule Status')
    parameter_name = 'schedule_status'
    default_value = 'pending'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will appear in the URL query.
        The second element is the human-readable name for the option that will
        appear in the right sidebar.
        """
        return (
            ('pending', _('Pending Approval')),
            ('all', _('All')),
            ('scheduled', _('Scheduled & Approved')),
            ('past_due', _('Past Due')),
            ('draft', _('Draft')),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via `self.value()`.
        """
        value = self.value() or self.default_value
        now = timezone.now()

        if value == 'pending':
            return queryset.filter(status='scheduled', is_approved=False, send_at__gt=now)
        if value == 'scheduled':
            return queryset.filter(status='scheduled', is_approved=True, send_at__gt=now)
        if value == 'past_due':
            return queryset.filter(status='scheduled', send_at__lt=now)
        if value == 'draft':
            return queryset.filter(status='draft')
        if value == 'all':
            return queryset
        return queryset

    def choices(self, changelist):
        """
        Override the default choices to prevent the automatic "All" link and
        to select our custom default.
        """
        value = self.value() or self.default_value
        for lookup, title in self.lookup_choices:
            yield {
                'selected': value == str(lookup),
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }


@admin.register(DraftMessage)
class DraftMessageAdmin(admin.ModelAdmin):
    list_display = ('message_preview',)
    list_filter = (
        DraftScheduleFilter,
        'status',
        'is_approved',
        'channel',
        'created_by',
    )
    search_fields = ('text', 'html', 'subject', 'to', 'cc', 'bcc', 'chat_id')
    readonly_fields = ('created_at', 'updated_at', 'sent_at', 'error_message', 'sent_message')
    actions = ['approve_drafts', 'unapprove_drafts']

    fieldsets = (
        (None, {
            'fields': ('channel',)
        }),
        (_('Message Content'), {
            'fields': ('text', 'html'),
            'classes': ('tinymce-content',),
        }),
        (_('Email Specific'), {
            'fields': ('to', 'cc', 'bcc', 'subject'),
            'classes': ('collapse',),
        }),
        (_('Chat Specific'), {
            'fields': ('chat_id',),
            'classes': ('collapse',),
        }),
        (_('Scheduling & Approval'), {
            'fields': ('send_at', 'is_approved', 'status'),
        }),
        (_('Metadata'), {
            'fields': ('created_by', 'created_at', 'updated_at', 'sent_at', 'sent_message', 'error_message'),
            'classes': ('collapse',),
        }),
    )

    class Media:
        css = {
            'all': (
                'admin/css/chat_list.css',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css',
            )
        }

    def save_model(self, request, obj, form, change):
        if not change:  # If this is a new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add TinyMCE for HTML content
        form.Media = type('Media', (), {
            'css': {'all': ('admin/css/forms.css',)},
            'js': (
                'unicom/js/tinymce_init.js',
            )
        })
        return form
    
    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'html':
            kwargs['widget'] = forms.Textarea(attrs={
                'class': 'tinymce',
                'data-tinymce': 'true'
            })
        return super().formfield_for_dbfield(db_field, **kwargs)

    def get_queryset(self, request):
        return super().get_queryset(request)

    def approve_drafts(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} draft(s) have been approved.')
    approve_drafts.short_description = 'Approve selected drafts'

    def unapprove_drafts(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} draft(s) have been unapproved.')
    unapprove_drafts.short_description = 'Unapprove selected drafts'

    def message_preview(self, obj):
        # Determine message type and status indicators
        is_email = obj.channel.platform == 'Email'
        is_pending = obj.status == 'scheduled' and not obj.is_approved
        is_past_due = obj.status == 'scheduled' and obj.send_at and obj.send_at < timezone.now()
        
        # Create status icons
        status_icons = format_html(
            '<span class="draft-status-icons">{}{}{}{}</span>',
            format_html('<i class="fas fa-clock text-warning" title="Pending Approval"></i>') if is_pending else '',
            format_html('<i class="fas fa-exclamation-circle text-danger" title="Past Due"></i>') if is_past_due else '',
            format_html('<i class="fas fa-check-circle text-success" title="Approved"></i>') if obj.is_approved else '',
            format_html('<i class="fas fa-envelope" title="Email"></i>') if is_email else format_html('<i class="fas fa-comment" title="Chat"></i>')
        )

        # Prepare content preview
        if is_email and obj.html:
            content_preview = format_html(
                '<div class="email-preview">{}</div>',
                mark_safe(obj.html)  # Safe because this is admin-only content
            )
        else:
            content_preview = obj.text if obj.text else 'No content'

        # Format recipients for email
        recipients = ''
        if is_email:
            to_list = ', '.join(obj.to) if obj.to else ''
            cc_list = f' (cc: {", ".join(obj.cc)})' if obj.cc else ''
            recipients = f'{to_list}{cc_list}' if to_list or cc_list else 'No recipients'

        return format_html('''
            <div class="draft-message-container">
                <div class="draft-header">
                    <div class="draft-title">
                        <span class="draft-subject">{}</span>
                        {}
                    </div>
                    <div class="draft-meta">
                        <span class="draft-channel">{}</span>
                        <span class="draft-time" title="Send At">{}</span>
                    </div>
                </div>
                {}
                <div class="draft-content">
                    {}
                </div>
                <div class="draft-footer">
                    <span class="draft-creator">By: {}</span>
                    <span class="draft-created">Created: {}</span>
                </div>
            </div>
            <style>
                .draft-message-container {{
                    padding: 15px;
                    border-radius: 4px;
                    background: var(--body-bg);
                    margin: 5px 0;
                }}
                .draft-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 10px;
                }}
                .draft-title {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .draft-subject {{
                    font-weight: bold;
                    font-size: 1.1em;
                    color: var(--link-fg);
                }}
                .draft-status-icons {{
                    display: flex;
                    gap: 8px;
                }}
                .draft-status-icons i {{
                    font-size: 1.1em;
                }}
                .text-warning {{
                    color: #f39c12;
                }}
                .text-danger {{
                    color: #e74c3c;
                }}
                .text-success {{
                    color: #2ecc71;
                }}
                .draft-meta {{
                    display: flex;
                    gap: 15px;
                    align-items: center;
                }}
                .draft-channel {{
                    background-color: var(--selected-row);
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 0.9em;
                }}
                .draft-time {{
                    color: var(--body-quiet-color);
                    font-size: 0.9em;
                }}
                .draft-recipients {{
                    font-size: 0.9em;
                    color: var(--body-quiet-color);
                    margin: 5px 0;
                }}
                .draft-content {{
                    margin: 10px 0;
                    padding: 10px;
                    background: var(--darkened-bg);
                    border-radius: 4px;
                    max-height: 300px;
                    overflow-y: auto;
                }}
                .email-preview {{
                    background: white !important;
                    padding: 15px !important;
                    border-radius: 4px !important;
                    /* Create a new stacking context to isolate styles */
                    position: relative !important;
                    z-index: 1 !important;
                }}
                /* Reset absolutely everything inside the preview */
                #container .email-preview *,
                #container .email-preview h1,
                #container .email-preview h2,
                #container .email-preview h3,
                #container .email-preview h4,
                #container .email-preview h5,
                #container .email-preview h6,
                #container .email-preview p,
                #container .email-preview span,
                #container .email-preview div,
                #container .email-preview table,
                #container .email-preview tr,
                #container .email-preview td,
                #container .email-preview th,
                #container .email-preview ul,
                #container .email-preview ol,
                #container .email-preview li,
                #container .email-preview a,
                #container .email-preview img,
                #container .email-preview blockquote,
                #container .email-preview pre,
                #container .email-preview code {{
                    all: revert !important;
                    font-family: revert !important;
                    color: initial !important;
                    background: initial !important;
                    padding: revert !important;
                    margin: revert !important;
                    border: revert !important;
                    font-size: revert !important;
                    font-weight: revert !important;
                    line-height: revert !important;
                    text-align: revert !important;
                    text-decoration: revert !important;
                    box-sizing: border-box !important;
                    width: revert !important;
                    height: revert !important;
                    min-width: revert !important;
                    min-height: revert !important;
                    max-width: revert !important;
                    max-height: revert !important;
                    display: revert !important;
                    position: revert !important;
                    top: revert !important;
                    left: revert !important;
                    right: revert !important;
                    bottom: revert !important;
                    float: revert !important;
                    clear: revert !important;
                    clip: revert !important;
                    visibility: revert !important;
                    overflow: revert !important;
                    vertical-align: revert !important;
                    white-space: revert !important;
                    word-break: revert !important;
                    word-wrap: revert !important;
                    word-spacing: revert !important;
                    letter-spacing: revert !important;
                    quotes: revert !important;
                    list-style: revert !important;
                    list-style-type: revert !important;
                    list-style-position: revert !important;
                    border-spacing: revert !important;
                    border-collapse: revert !important;
                    caption-side: revert !important;
                    table-layout: revert !important;
                    empty-cells: revert !important;
                    opacity: revert !important;
                    transform: none !important;
                    transition: none !important;
                    box-shadow: none !important;
                    text-shadow: none !important;
                    text-transform: none !important;
                    flex: none !important;
                    flex-flow: none !important;
                    flex-basis: auto !important;
                    flex-direction: row !important;
                    flex-grow: 0 !important;
                    flex-shrink: 1 !important;
                    flex-wrap: nowrap !important;
                    justify-content: normal !important;
                    align-items: normal !important;
                    align-content: normal !important;
                    order: 0 !important;
                    filter: none !important;
                    backdrop-filter: none !important;
                    perspective: none !important;
                    -webkit-font-smoothing: auto !important;
                    -moz-osx-font-smoothing: auto !important;
                }}
                /* Additional specific overrides for problematic elements */
                #container .email-preview h1,
                #container .email-preview h2,
                #container .email-preview h3,
                #container .email-preview h4,
                #container .email-preview h5,
                #container .email-preview h6 {{
                    background: none !important;
                    border: none !important;
                    color: #000 !important;
                    padding: revert !important;
                    margin: 0.67em 0 !important;
                    font-weight: bold !important;
                }}
                #container .email-preview h1 {{ font-size: 2em !important; }}
                #container .email-preview h2 {{ font-size: 1.5em !important; }}
                #container .email-preview h3 {{ font-size: 1.17em !important; }}
                #container .email-preview h4 {{ font-size: 1em !important; }}
                #container .email-preview h5 {{ font-size: 0.83em !important; }}
                #container .email-preview h6 {{ font-size: 0.67em !important; }}
                /* Ensure tables render properly */
                #container .email-preview table {{
                    display: table !important;
                    border-collapse: separate !important;
                    border-spacing: 2px !important;
                    box-sizing: border-box !important;
                    text-indent: initial !important;
                    border-color: gray !important;
                }}
                #container .email-preview table td,
                #container .email-preview table th {{
                    padding: 1px !important;
                    border-color: inherit !important;
                }}
                /* Ensure lists render properly */
                #container .email-preview ul {{
                    list-style-type: disc !important;
                    margin: 1em 0 !important;
                    padding-left: 40px !important;
                }}
                #container .email-preview ol {{
                    list-style-type: decimal !important;
                    margin: 1em 0 !important;
                    padding-left: 40px !important;
                }}
                /* Ensure links render properly */
                #container .email-preview a {{
                    color: #0000EE !important;
                    text-decoration: underline !important;
                    cursor: pointer !important;
                }}
                #container .email-preview a:visited {{
                    color: #551A8B !important;
                }}
                .draft-footer {{
                    display: flex;
                    justify-content: space-between;
                    font-size: 0.8em;
                    color: var(--body-quiet-color);
                    margin-top: 10px;
                }}
            </style>
        ''',
        obj.subject or 'No Subject',
        status_icons,
        obj.channel,
        obj.send_at.strftime('%Y-%m-%d %H:%M') if obj.send_at else 'No schedule',
        format_html('<div class="draft-recipients">{}</div>', recipients) if recipients else '',
        content_preview,
        (obj.created_by.get_full_name() or obj.created_by.username) if obj.created_by else 'Unknown',
        obj.created_at.strftime('%Y-%m-%d %H:%M')
        )
    message_preview.short_description = 'Draft Messages'

class EmailInlineImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'email_message', 'created_at', 'serving_link')
    readonly_fields = ('serving_link',)

    def serving_link(self, obj):
        if not obj.pk:
            return "(save to get link)"
        shortid = obj.get_short_id()
        path = reverse('inline_image', kwargs={'shortid': shortid})
        url = f"{get_public_origin().rstrip('/')}{path}"
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)
    serving_link.short_description = "Serving Link"

class MessageTemplateInlineImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'template', 'created_at', 'serving_link')
    readonly_fields = ('serving_link',)

    def serving_link(self, obj):
        if not obj.pk:
            return "(save to get link)"
        shortid = obj.get_short_id()
        path = reverse('template_inline_image', kwargs={'shortid': shortid})
        url = f"{get_public_origin().rstrip('/')}{path}"
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)
    serving_link.short_description = "Serving Link"

admin.site.register(Channel, ChannelAdmin)
admin.site.register(Message)
admin.site.register(Update)
admin.site.register(Chat, ChatAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(AccountChat, AccountChatAdmin)
admin.site.register(EmailInlineImage, EmailInlineImageAdmin)
admin.site.register(MessageTemplateInlineImage, MessageTemplateInlineImageAdmin)
