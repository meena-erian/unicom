"""
WebChat API views.
Handles REST API endpoints for WebChat functionality.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.middleware import SessionMiddleware
from unicom.models import Channel, Message, Chat, AccountChat
from unicom.services.webchat.save_webchat_message import save_webchat_message
from unicom.services.webchat.get_or_create_account import get_or_create_account


def _get_webchat_channel():
    """Get the first active WebChat channel."""
    channel = Channel.objects.filter(platform='WebChat', active=True).first()
    if not channel:
        raise ValueError("No active WebChat channel found")
    return channel


def _ensure_session(request):
    """Ensure request has a session (for guest users)."""
    if not hasattr(request, 'session'):
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()


@csrf_exempt  # We'll handle CSRF manually to support both session and token auth
@require_http_methods(["POST"])
def send_webchat_message_api(request):
    """
    Send a message from user to WebChat.

    POST /unicom/webchat/send/

    Request body (form data or JSON):
        - text: Message text (required unless media is provided)
        - chat_id: Chat ID (optional - auto-creates if not provided)
        - media: File upload (optional)

    Returns:
        JSON with message details and chat_id
    """
    try:
        _ensure_session(request)

        # Get channel
        channel = _get_webchat_channel()

        # Extract data
        if request.content_type and 'application/json' in request.content_type:
            import json
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            chat_id = data.get('chat_id')
            media_file = None
        else:
            text = request.POST.get('text', '').strip()
            chat_id = request.POST.get('chat_id')
            media_file = request.FILES.get('media')

        # Validate
        if not text and not media_file:
            return JsonResponse({'error': 'Either text or media is required'}, status=400)

        # Determine media type
        media_type = 'text'
        if media_file:
            content_type = media_file.content_type
            if content_type.startswith('image/'):
                media_type = 'image'
            elif content_type.startswith('audio/'):
                media_type = 'audio'

        # Extract optional metadata for chat creation
        chat_metadata = {}
        if request.content_type and 'application/json' in request.content_type:
            chat_metadata = data.get('metadata', {})
        else:
            # Parse metadata from form data if provided as JSON string
            metadata_str = request.POST.get('metadata')
            if metadata_str:
                import json
                try:
                    chat_metadata = json.loads(metadata_str)
                except json.JSONDecodeError:
                    pass

        # Build message data
        message_data = {
            'text': text or f'**{media_type.title()}**',
            'chat_id': chat_id,
            'media_type': media_type,
            'file': media_file,
            'metadata': chat_metadata,  # Pass metadata for new chat creation
        }

        # Save message
        message = save_webchat_message(channel, message_data, request, user=request.user if request.user.is_authenticated else None)

        if not message:
            return JsonResponse({'error': 'Message could not be sent (account blocked)'}, status=403)

        # Return response
        return JsonResponse({
            'success': True,
            'chat_id': message.chat_id,
            'message': {
                'id': message.id,
                'text': message.text,
                'timestamp': message.timestamp.isoformat(),
                'chat_id': message.chat_id,
                'media_type': message.media_type,
                'media_url': message.media.url if message.media else None,
                'is_outgoing': message.is_outgoing,
                'sender_name': message.sender_name,
            }
        })

    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Internal server error: {str(e)}'}, status=500)


@require_http_methods(["GET"])
def get_webchat_messages_api(request):
    """
    Get messages for a chat with optional filtering.

    GET /unicom/webchat/messages/

    Query parameters:
        - chat_id: Chat ID (optional - defaults to user's default chat)
        - limit: Max messages to return (default: 50, max: 100)
        - before: Message ID cursor for pagination (get messages before this)
        - after: Message ID cursor for pagination (get messages after this)
        - is_outgoing: Filter by message direction (true/false)
        - media_type: Filter by media type (text/image/audio)
        - sender_name: Filter by sender name

    Returns:
        JSON with list of messages
    """
    try:
        _ensure_session(request)

        # Get channel
        channel = _get_webchat_channel()

        # Get account
        account = get_or_create_account(channel, request)

        # Get parameters
        chat_id = request.GET.get('chat_id')
        limit = min(int(request.GET.get('limit', 50)), 100)
        before = request.GET.get('before')
        after = request.GET.get('after')

        # If no chat_id provided, return empty list
        if not chat_id:
            return JsonResponse({
                'success': True,
                'chat_id': None,
                'messages': [],
                'has_more': False,
                'next_cursor': None
            })

        # Verify access to chat
        try:
            chat = Chat.objects.get(id=chat_id, platform='WebChat')
            AccountChat.objects.get(account=account, chat=chat)
        except (Chat.DoesNotExist, AccountChat.DoesNotExist):
            return JsonResponse({'error': 'Chat not found or access denied'}, status=404)

        # Build query
        messages = Message.objects.filter(chat=chat).order_by('-timestamp')

        # Apply custom filters
        reserved_params = {'chat_id', 'limit', 'before', 'after'}
        for key, value in request.GET.items():
            if key in reserved_params:
                continue

            # Convert booleans
            if value.lower() in ['true', 'false']:
                value = value.lower() == 'true'

            # Apply filter if it's a valid Message field
            if hasattr(Message, key):
                messages = messages.filter(**{key: value})

        # Apply cursor pagination
        if before:
            try:
                before_msg = Message.objects.get(id=before)
                messages = messages.filter(timestamp__lt=before_msg.timestamp)
            except Message.DoesNotExist:
                pass

        if after:
            try:
                after_msg = Message.objects.get(id=after)
                messages = messages.filter(timestamp__gt=after_msg.timestamp)
            except Message.DoesNotExist:
                pass

        # Fetch messages
        messages_list = list(messages[:limit + 1])  # +1 to check if there are more
        has_more = len(messages_list) > limit
        if has_more:
            messages_list = messages_list[:limit]

        # Reverse to get chronological order
        messages_list.reverse()

        # Serialize messages
        messages_data = [{
            'id': msg.id,
            'text': msg.text,
            'html': msg.html,
            'is_outgoing': msg.is_outgoing,
            'sender_name': msg.sender_name,
            'timestamp': msg.timestamp.isoformat(),
            'media_type': msg.media_type,
            'media_url': msg.media.url if msg.media else None,
        } for msg in messages_list]

        return JsonResponse({
            'success': True,
            'chat_id': chat_id,
            'messages': messages_data,
            'has_more': has_more,
            'next_cursor': messages_list[0].id if messages_list and has_more else None
        })

    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Internal server error: {str(e)}'}, status=500)


@require_http_methods(["GET"])
def list_webchat_chats_api(request):
    """
    List chats for current user with custom filtration support.

    GET /unicom/webchat/chats/

    Query parameters:
        - channel_id: Filter by channel (optional)
        - Any Chat model field for filtering (e.g., is_archived=false)
        - metadata__<key>: Filter by metadata fields (e.g., metadata__project_id=123)
        - metadata__<key>__<lookup>: Advanced lookups (e.g., metadata__priority__gte=5)

    Examples:
        - ?is_archived=false - Only non-archived chats
        - ?metadata__project_id=123 - Chats for project 123
        - ?metadata__department=sales - Chats for sales department
        - ?metadata__priority__gte=5 - Chats with priority >= 5

    Returns:
        JSON with list of chats
    """
    try:
        _ensure_session(request)

        # Get channel
        channel = _get_webchat_channel()

        # Get account
        account = get_or_create_account(channel, request)

        # Build query for chats where user is a participant
        chats = Chat.objects.filter(
            platform='WebChat',
            accountchat__account=account
        )

        # Apply filters from query parameters
        channel_id = request.GET.get('channel_id')
        if channel_id:
            chats = chats.filter(channel_id=channel_id)

        # Apply standard Chat model field filters and metadata filters
        filter_params = {}
        reserved_params = {'channel_id', 'limit', 'offset', 'ordering'}

        for key, value in request.GET.items():
            if key in reserved_params:
                continue

            # Check if this is a metadata filter
            if key.startswith('metadata__'):
                # Support metadata lookups like metadata__project_id, metadata__priority__gte
                # Convert string booleans and numbers
                if value.lower() in ['true', 'false']:
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)
                elif value.replace('.', '', 1).isdigit() and value.count('.') == 1:
                    value = float(value)

                filter_params[key] = value

            # Check if this is a standard Chat model field
            elif hasattr(Chat, key.split('__')[0]):
                # Support field lookups like is_archived, name__icontains
                if value.lower() in ['true', 'false']:
                    value = value.lower() == 'true'
                filter_params[key] = value

        if filter_params:
            chats = chats.filter(**filter_params)

        # Order by most recent
        chats = chats.order_by('-last_message__timestamp')

        # Serialize chats
        chats_data = []
        for chat in chats:
            last_msg = chat.last_message
            chat_data = {
                'id': chat.id,
                'name': chat.name,
                'platform': chat.platform,
                'channel_id': chat.channel_id,
                'is_archived': chat.is_archived,
                'metadata': chat.metadata,  # Include metadata in response
                'last_message': {
                    'text': last_msg.text if last_msg else None,
                    'timestamp': last_msg.timestamp.isoformat() if last_msg else None,
                } if last_msg else None
            }
            chats_data.append(chat_data)

        return JsonResponse({
            'success': True,
            'chats': chats_data
        })

    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Internal server error: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["PATCH", "PUT"])
def update_webchat_chat_api(request, chat_id):
    """
    Update chat (rename title or archive status).

    PATCH/PUT /unicom/webchat/chat/<chat_id>/

    Request body:
        - title: New chat title (optional)
        - is_archived: Archive status (optional)

    Returns:
        JSON with updated chat details
    """
    try:
        _ensure_session(request)

        # Get channel
        channel = _get_webchat_channel()

        # Get account
        account = get_or_create_account(channel, request)

        # Parse request body
        import json
        data = json.loads(request.body)

        # Verify access to chat
        try:
            chat = Chat.objects.get(id=chat_id, platform='WebChat')
            AccountChat.objects.get(account=account, chat=chat)
        except (Chat.DoesNotExist, AccountChat.DoesNotExist):
            return JsonResponse({'error': 'Chat not found or access denied'}, status=404)

        # Update fields
        updated_fields = []

        if 'title' in data:
            chat.name = data['title']
            updated_fields.append('name')

        if 'is_archived' in data:
            chat.is_archived = data['is_archived']
            updated_fields.append('is_archived')

        if updated_fields:
            chat.save(update_fields=updated_fields)

        return JsonResponse({
            'success': True,
            'chat': {
                'id': chat.id,
                'name': chat.name,
                'is_archived': chat.is_archived,
            }
        })

    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Internal server error: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_webchat_chat_api(request, chat_id):
    """
    Delete/archive a chat.

    DELETE /unicom/webchat/chat/<chat_id>/

    Query parameters:
        - hard_delete: If 'true', permanently delete. Otherwise archive (default).

    Returns:
        JSON with success message
    """
    try:
        _ensure_session(request)

        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        # Get channel
        channel = _get_webchat_channel()

        # Get account
        account = get_or_create_account(channel, request)

        # Verify access to chat
        try:
            chat = Chat.objects.get(id=chat_id, platform='WebChat')
            AccountChat.objects.get(account=account, chat=chat)
        except (Chat.DoesNotExist, AccountChat.DoesNotExist):
            return JsonResponse({'error': 'Chat not found or access denied'}, status=404)

        # Check if hard delete requested
        hard_delete = request.GET.get('hard_delete', 'false').lower() == 'true'

        if hard_delete:
            # Permanently delete chat and all messages
            chat.delete()
            message = 'Chat permanently deleted'
        else:
            # Soft delete: archive
            chat.is_archived = True
            chat.save(update_fields=['is_archived'])
            message = 'Chat archived'

        return JsonResponse({
            'success': True,
            'message': message
        })

    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Internal server error: {str(e)}'}, status=500)
