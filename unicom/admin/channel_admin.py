from django.contrib import admin
from django.db import models
from django_ace import AceWidget
from ..models import Channel

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