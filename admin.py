from django.contrib import admin
from unicom.models import Message, Update, Chat, Account, AccountChat, Bot
from django.utils.html import format_html
from unicom.views.chat_history_view import chat_history_view
from django.urls import path


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

class BotAdmin(admin.ModelAdmin):
    list_filter = ('platform', )
    search_fields = ('name', )
    list_display = ('id', 'name', 'platform', 'active', 'confirmed_webhook_url', 'error')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['active', 'confirmed_webhook_url', 'error']
        return super().get_readonly_fields(request, obj)

admin.site.register(Bot)
admin.site.register(Message)
admin.site.register(Update)
admin.site.register(Chat, ChatAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(AccountChat, AccountChatAdmin)
