from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from unicom.models import Channel
from django.core.exceptions import ValidationError


@staff_member_required
def compose_view(request):
    # Store initial form data
    form_data = {
        'channel': request.POST.get('channel', ''),
        'to': request.POST.get('to', ''),
        'cc': request.POST.get('cc', ''),
        'bcc': request.POST.get('bcc', ''),
        'subject': request.POST.get('subject', ''),
        'html': request.POST.get('html', ''),
        'chat_id': request.POST.get('chat_id', ''),
        'text': request.POST.get('text', '')
    }
    
    if request.method == 'POST':
        channel_id = request.POST.get('channel')
        try:
            channel = Channel.objects.get(id=channel_id)
            
            # Prepare message parameters based on platform
            if channel.platform == 'Email':
                # Split comma-separated email addresses into lists
                to_list = [email.strip() for email in request.POST.get('to', '').split(',') if email.strip()]
                cc_list = [email.strip() for email in request.POST.get('cc', '').split(',') if email.strip()]
                bcc_list = [email.strip() for email in request.POST.get('bcc', '').split(',') if email.strip()]
                
                msg_params = {
                    'to': to_list,
                    'cc': cc_list,
                    'bcc': bcc_list,
                    'subject': request.POST.get('subject'),
                    'html': request.POST.get('html'),
                }
                
                # Validate required fields for email
                if not to_list:
                    raise ValidationError("At least one recipient is required")
                if not msg_params['subject']:
                    raise ValidationError("Subject is required")
                if not msg_params['html']:
                    raise ValidationError("Message body is required")
                
            elif channel.platform == 'Telegram':
                msg_params = {
                    'chat_id': request.POST.get('chat_id'),
                    'text': request.POST.get('text'),
                    'parse_mode': 'Markdown'
                }
                
                # Validate required fields for telegram
                if not msg_params['chat_id']:
                    raise ValidationError("Chat ID is required")
                if not msg_params['text']:
                    raise ValidationError("Message text is required")
            
            else:
                raise ValidationError(f"Unsupported platform: {channel.platform}")
            
            # Send the message
            channel.send_message(msg_params, request.user)
            messages.success(request, 'Message sent successfully!')
            return redirect('admin:unicom_chat_changelist')
            
        except Channel.DoesNotExist:
            messages.error(request, 'Invalid channel selected.')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error sending message: {str(e)}')

    t_key = getattr(settings, 'UNICOM_TINYMCE_API_KEY', None)
    
    # For GET requests or if POST fails, show the form
    context = {
        'channels': Channel.objects.filter(active=True),
        'tinymce_api_key': t_key,
        'title': 'Compose Message',
        'form_data': form_data  # Pass the form data back to the template
    }
    return render(request, 'admin/unicom/chat/compose.html', context) 