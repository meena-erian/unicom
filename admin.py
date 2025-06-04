from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _
from unicom.models import Message, Update, Chat, Account, AccountChat, Channel
from django.utils.html import format_html
from unicom.views.chat_history_view import chat_history_view
from unicom.views.compose_view import compose_view
from django.urls import path
from django_ace import AceWidget
from .models import (
    Member,
    MemberGroup,
    RequestCategory,
    Request,
    MessageTemplate,
)
from django import forms
from django.conf import settings


class ChatAdmin(admin.ModelAdmin):
    list_filter = ('platform', 'is_private', 'channel')
    list_display = ('chat_info',)
    search_fields = ('id', 'name', 'messages__text', 'messages__sender__name')

    class Media:
        css = {
            'all': ('admin/css/chat_list.css',)
        }

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Annotate the queryset with the last message information
        return qs.annotate(
            last_message_time=models.Max('messages__timestamp'),
            last_message_text=models.Subquery(
                Message.objects.filter(chat=models.OuterRef('pk'))
                .order_by('-timestamp')
                .values('text')[:1]
            )
        ).order_by('-last_message_time')

    def chat_info(self, obj):
        name = obj.name or obj.id
        last_message = obj.last_message_text[:100] + '...' if obj.last_message_text and len(obj.last_message_text) > 100 else obj.last_message_text or 'No messages'
        
        return format_html('''
            <a href="{}" class="chat-info-container">
                <div class="chat-header">
                    <span class="chat-name">{}</span>
                </div>
                <div class="chat-message">
                    {}
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
                .chat-header {{
                    margin-bottom: 5px;
                }}
                .chat-name {{
                    font-weight: bold;
                    font-size: 1.1em;
                    color: var(--link-fg);
                }}
                .chat-message {{
                    color: var(--body-fg);
                    margin-bottom: 5px;
                    font-size: 0.9em;
                    opacity: 0.9;
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
        name,
        last_message,
        obj.channel,
        obj.last_message_time.strftime('%Y-%m-%d %H:%M') if obj.last_message_time else 'Never'
        )
    chat_info.short_description = 'Chats'
    chat_info.admin_order_field = '-last_message_time'

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
        # Add TinyMCE API key to the form's Media
        form.Media = type('Media', (), {
            'css': {'all': ('admin/css/forms.css',)},
            'js': (
                f'https://cdn.tiny.cloud/1/{settings.UNICOM_TINYMCE_API_KEY}/tinymce/6/tinymce.min.js',
                'unicom/js/tinymce_init.js',
            )
        })
        return form

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'content':
            kwargs['widget'] = forms.Textarea(attrs={
                'class': 'tinymce',
                'data-tinymce': 'true'
            })
        return super().formfield_for_dbfield(db_field, **kwargs)

admin.site.register(Channel, ChannelAdmin)
admin.site.register(Message)
admin.site.register(Update)
admin.site.register(Chat, ChatAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(AccountChat, AccountChatAdmin)
