from django.contrib import admin
from django.db import models
from unicom.models import Message, Update, Chat, Account, AccountChat, Channel
from django.utils.html import format_html
from unicom.views.chat_history_view import chat_history_view
from django.urls import path
from django_ace import AceWidget
from .models import (
    Member,
    MemberGroup,
    RequestCategory,
    Request,
)


class ChatAdmin(admin.ModelAdmin):
    list_filter = ('platform', 'is_private')
    list_display = ('id', 'name', 'view_chat_link')
    search_fields = ('id', 'name') 

    def view_chat_link(self, obj):
        return format_html('<a href="{}" target="_blank">View Chat</a>', self.url_for_chat(obj.id))

    def url_for_chat(self, id):
        return f"{id}/messages/"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:chat_id>/messages/', self.admin_site.admin_view(chat_history_view), name='chat-detail')
        ]
        return custom_urls + urls

    view_chat_link.short_description = 'View Chat'


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

admin.site.register(Channel, ChannelAdmin)
admin.site.register(Message)
admin.site.register(Update)
admin.site.register(Chat, ChatAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(AccountChat, AccountChatAdmin)
