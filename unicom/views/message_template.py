from django.http import JsonResponse
from django.views.generic import View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from ..models import MessageTemplate, Channel

"""
This view is an API endpoint used to serve message templates to TinyMCE.
It allows for filtering templates by channel.
"""

@method_decorator(login_required, name='dispatch')
class MessageTemplateListView(View):
    """View to serve message templates to TinyMCE."""
    
    def get(self, request, *args, **kwargs):
        # Get channel_id from query params if provided
        channel_id = request.GET.get('channel_id')
        
        # Base queryset
        templates = MessageTemplate.objects.all()
        
        # Filter by channel if specified
        if channel_id:
            try:
                channel = Channel.objects.get(id=channel_id)
                templates = templates.filter(Q(channels=channel) | Q(channels__isnull=True))
            except Channel.DoesNotExist:
                templates = templates.filter(channels__isnull=True)
        
        # Convert to TinyMCE template format
        tinymce_templates = []
        for template in templates:
            tinymce_templates.append({
                'title': template.title,
                'description': template.description,
                'content': template.content,
            })
        
        return JsonResponse(tinymce_templates, safe=False) 