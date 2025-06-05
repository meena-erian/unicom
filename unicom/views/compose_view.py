from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from unicom.models import Channel, DraftMessage
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.dateparse import parse_datetime


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
        'text': request.POST.get('text', ''),
        'send_at': request.POST.get('send_at', '')
    }
    
    if request.method == 'POST':
        channel_id = request.POST.get('channel')
        send_at = request.POST.get('send_at')
        
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
                }
                
                # Validate required fields for telegram
                if not msg_params['chat_id']:
                    raise ValidationError("Chat ID is required")
                if not msg_params['text']:
                    raise ValidationError("Message text is required")
            
            else:
                raise ValidationError(f"Unsupported platform: {channel.platform}")
            
            # If send_at is set, create a draft message instead of sending immediately
            if send_at:
                draft = DraftMessage(
                    channel=channel,
                    created_by=request.user,
                    status='scheduled',
                    is_approved=True,
                    send_at=parse_datetime(send_at)
                )
                
                # Set platform-specific fields
                if channel.platform == 'Email':
                    draft.to = msg_params['to']
                    draft.cc = msg_params['cc']
                    draft.bcc = msg_params['bcc']
                    draft.subject = msg_params['subject']
                    draft.html = msg_params['html']
                else:  # Telegram
                    draft.chat_id = msg_params['chat_id']
                    draft.text = msg_params['text']
                
                draft.full_clean()  # Validate the draft
                draft.save()
                messages.success(request, 'Message scheduled successfully!')
                return redirect('admin:unicom_draftmessage_changelist')
            
            # If no send_at, send immediately (existing logic)
            else:
                message = channel.send_message(msg_params, request.user)
                messages.success(request, 'Message sent successfully!')
                return redirect(
                    reverse('admin:chat-detail', args=[message.chat.id])
                )
            
        except Channel.DoesNotExist:
            messages.error(request, 'Invalid channel selected.')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    t_key = getattr(settings, 'UNICOM_TINYMCE_API_KEY', None)
    
    # For GET requests or if POST fails, show the form
    context = {
        'channels': Channel.objects.filter(active=True),
        'tinymce_api_key': t_key,
        'form_data': form_data
    }
    return render(request, 'admin/unicom/chat/compose.html', context) 