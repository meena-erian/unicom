from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from unicom.models import Message, Chat
from django.contrib.auth.decorators import login_required


@login_required
def chat_history_view(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    message_list = list(
        Message.objects
            .filter(chat_id=chat_id)
            .order_by('-timestamp')[:100]
    )[::-1]

    if request.method == 'POST':
        message_type = request.POST.get('message_type', 'text')
        reply_to_id = request.POST.get('reply_to_id')
        msg_dict = {}

        if message_type == 'email':
            message_html = request.POST.get('message_html', '').strip()
            # Only use custom subject if it was actually modified
            subject = request.POST.get('subject', '').strip()
            original_subject = request.POST.get('original_subject', '').strip()
            
            if message_html:
                msg_dict = {
                    'html': message_html,
                }
                # Only include subject if it differs from the original
                if subject and subject != original_subject:
                    msg_dict['subject'] = subject
        else:
            message_text = request.POST.get('message_text', '').strip()
            if message_text:
                msg_dict = {'text': message_text}

        if msg_dict:
            if reply_to_id:
                msg_dict['reply_to_message_id'] = reply_to_id
                
            chat.send_message(msg_dict, user=request.user)
            return HttpResponseRedirect(request.path_info)

    # Additional context for email chats
    last_message = message_list[-1] if message_list else None
    show_recipients = False

    if chat.platform == 'Email' and last_message:
        # Determine whether to render recipient headers.
        # For outgoing messages, always show recipients
        if last_message.is_outgoing:
            show_recipients = True
        else:
            # For incoming messages, show if multiple recipients
            recipients_set = set((last_message.to or []) + (last_message.cc or []) + (last_message.bcc or []))
            if len(recipients_set) > 1:
                show_recipients = True

    # Determine subject line to display (primarily for email threads)
    subject_line = chat.name
    if chat.platform == 'Email' and last_message and last_message.subject:
        subject_line = last_message.subject

    return render(
        request,
        'admin/unicom/chat_history.html',
        {
            'chat': chat,
            'chat_messages_list': message_list,
            'without_messages': True,  # This will be used to suppress the toast
            # Expose TinyMCE Cloud API key (if set) for the email composer template
            'tinymce_api_key': getattr(settings, 'UNICOM_TINYMCE_API_KEY', ''),
            'last_message': last_message,
            'show_recipients': show_recipients,
            'subject_line': subject_line,
            'channel_id': chat.channel_id if hasattr(chat, 'channel_id') else None,
        },
    )
