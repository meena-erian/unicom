from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
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
        message_text = request.POST.get('message_text', '')
        reply_to_id = request.POST.get('reply_to_id')
        
        if message_text.strip():
            msg_dict = {'text': message_text}
            if reply_to_id:
                msg_dict['reply_to_message_id'] = reply_to_id
                
            chat.send_message(msg_dict, user=request.user)
            return HttpResponseRedirect(request.path_info)

    return render(request, 'admin/unicom/chat_history.html', {
        'chat': chat,
        'chat_messages_list': message_list,
        'without_messages': True  # This will be used to suppress the toast
    })
