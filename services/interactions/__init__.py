"""Persistence and dispatch shared by web and Telegram."""
import json
import logging
from dataclasses import asdict
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from unicom.interactions import Complete, InteractionContext, MessageWithButtons, resolve_handler
from unicom.models import CallbackExecution, Interaction, Request, ToolCall

logger = logging.getLogger(__name__)


def _validate(prompt):
    if not isinstance(prompt.text, str) or not prompt.text.strip() or len(prompt.text) > 3500:
        raise ValueError("Interaction text must contain 1–3500 characters")
    buttons = [asdict(button) for button in prompt.buttons]
    if not 1 <= len(buttons) <= 20 or len({b['action'] for b in buttons}) != len(buttons):
        raise ValueError("Provide 1–20 uniquely named actions")
    for button in buttons:
        if not button['action'] or len(button['action']) > 64 or not button['text'] or len(button['text']) > 64:
            raise ValueError("Button action and label must contain 1–64 characters")
        if button['style'] not in ('primary', 'secondary', 'danger'):
            raise ValueError("Unknown button style")
    if not 1 <= prompt.expires_in <= 604800:
        raise ValueError("Expiry must be between one second and seven days")
    json.dumps([prompt.state, prompt.presentation], allow_nan=False)
    return buttons


def _callbacks(interaction):
    buttons = []
    for button in interaction.buttons:
        callback = CallbackExecution.objects.create(
            original_message=interaction.message, intended_account=interaction.account,
            tool_call=interaction.tool_call, expires_at=interaction.expires_at,
            callback_data={'interaction': str(interaction.pk), 'revision': interaction.revision, 'action': button['action']},
        )
        buttons.append({**button, 'type': 'callback', 'callback_execution_id': str(callback.pk)})
    interaction.buttons = buttons
    interaction.save(update_fields=['buttons'])


def public_state(interaction):
    """Only explicitly public presentation data crosses the transport boundary."""
    expired = interaction.status == 'awaiting_input' and interaction.expires_at <= timezone.now()
    return {
        'id': str(interaction.pk), 'callId': interaction.tool_call.call_id,
        'toolName': interaction.tool_call.tool_name, 'status': 'expired' if expired else interaction.status,
        'revision': interaction.revision, 'text': 'This request has expired.' if expired else interaction.text,
        'data': interaction.presentation, 'component': interaction.component,
        'buttons': interaction.buttons if interaction.status == 'awaiting_input' and not expired else [],
        'expiresAt': interaction.expires_at.isoformat(),
    }


def _publish_telegram(interaction_id):
    """Best-effort projection; persisted state is authoritative for stale buttons."""
    try:
        interaction = Interaction.objects.select_related('message__channel').get(pk=interaction_id)
        if interaction.message.platform != 'Telegram':
            return
        from unicom.services.telegram.edit_telegram_message import edit_telegram_message
        state = public_state(interaction)
        buttons = [{'text': b['text'], 'callback_data': b['callback_execution_id']} for b in state['buttons']]
        rows = [buttons[index:index + 3] for index in range(0, len(buttons), 3)]
        edit_telegram_message(interaction.message.channel, interaction.message, {
            'text': state['text'], 'parse_mode': '', 'reply_markup': {'inline_keyboard': rows},
        })
    except Exception:
        logger.exception('Could not update Telegram interaction %s', interaction_id)


def _publish(interaction):
    # Updating the ordinary message also gives non-rich clients a readable summary.
    interaction.message.text = interaction.text
    interaction.message.save(update_fields=['text'])
    transaction.on_commit(lambda pk=interaction.pk: _publish_telegram(pk))


def start_interaction(prompt, tool_call):
    buttons = _validate(prompt)
    handler = resolve_handler(prompt.handler_key)
    if not issubclass(handler, MessageWithButtons):
        raise ValueError("Interaction handler is not registered")
    if tool_call.initial_user_message.platform not in ('WebChat', 'Telegram'):
        raise ValueError("Interactive tools require WebChat or Telegram")
    with transaction.atomic():
        Request.objects.select_for_update().get(pk=tool_call.request_id)
        tool_call = ToolCall.objects.select_for_update().get(pk=tool_call.pk)
        existing = Interaction.objects.filter(tool_call=tool_call).first()
        if existing:
            return existing
        if tool_call.status not in ('PENDING', 'IN_PROGRESS'):
            raise ValueError("Tool call is no longer pending")
        message = tool_call.initial_user_message.reply_with({'text': prompt.text, 'parse_mode': ''})
        if message is None:
            raise ValueError("Interaction message was not delivered")
        interaction = Interaction.objects.create(
            tool_call=tool_call, account=tool_call.request.account, message=message,
            handler=prompt.handler_key, state=prompt.state, presentation=prompt.presentation,
            component=handler.web_component or {}, buttons=buttons, text=prompt.text,
            expires_at=timezone.now() + timedelta(seconds=prompt.expires_in),
        )
        _callbacks(interaction)
        _publish(interaction)
        return interaction


def _finish(interaction, completion, status=None):
    json.dumps([completion.result, completion.presentation], allow_nan=False)
    interaction.result = completion.result
    interaction.presentation = completion.presentation
    interaction.text = completion.text
    interaction.status = status or ('cancelled' if completion.cancelled else 'completed')
    interaction.revision += 1
    interaction.save()
    _publish(interaction)
    interaction.tool_call.respond(completion.result, status='ERROR' if status in ('expired', 'error') else 'SUCCESS')


def dispatch(execution, account):
    """Return None for legacy callbacks; otherwise an idempotent interaction state."""
    data = execution.callback_data
    if not isinstance(data, dict) or 'interaction' not in data:
        return None
    with transaction.atomic():
        # Consistent lock order also serializes sibling tool completions.
        Request.objects.select_for_update().get(pk=execution.tool_call.request_id)
        interaction = Interaction.objects.select_for_update().select_related('message', 'tool_call').get(pk=data['interaction'])
        if (interaction.account_id != account.pk or execution.intended_account_id != account.pk
                or execution.original_message_id != interaction.message_id
                or execution.tool_call_id != interaction.tool_call_id):
            raise PermissionDenied("This interaction belongs to another account")
        if interaction.status != 'awaiting_input':
            return public_state(interaction)
        if interaction.expires_at <= timezone.now():
            _finish(interaction, Complete({'expired': True}, text='This request has expired.'), 'expired')
            return public_state(interaction)
        if data.get('revision') != interaction.revision:
            raise ValidationError("This button belongs to an earlier step")
        if data.get('action') not in {b['action'] for b in interaction.buttons}:
            raise ValidationError("Unknown action")
        cls = resolve_handler(interaction.handler)
        handler = cls(state=interaction.state, presentation=interaction.presentation)
        context = InteractionContext(interaction, account, interaction.tool_call)
        outcome = handler.on_action(data['action'], context)
        if isinstance(outcome, Complete):
            _finish(interaction, outcome)
        elif isinstance(outcome, MessageWithButtons):
            buttons = _validate(outcome)
            resolve_handler(outcome.handler_key)
            interaction.handler = outcome.handler_key
            interaction.state = outcome.state
            interaction.presentation = outcome.presentation
            interaction.component = resolve_handler(outcome.handler_key).web_component or {}
            interaction.buttons = buttons
            interaction.text = outcome.text
            interaction.revision += 1
            interaction.save()
            _callbacks(interaction)
            _publish(interaction)
        else:
            raise ValueError("on_action must return Complete or MessageWithButtons")
        return public_state(interaction)


def expire_interactions():
    for pk in Interaction.objects.filter(status='awaiting_input', expires_at__lte=timezone.now()).values_list('pk', flat=True):
        with transaction.atomic():
            candidate = Interaction.objects.select_related('tool_call').get(pk=pk)
            Request.objects.select_for_update().get(pk=candidate.tool_call.request_id)
            interaction = Interaction.objects.select_for_update().select_related('message', 'tool_call').get(pk=pk)
            if interaction.status == 'awaiting_input':
                _finish(interaction, Complete({'expired': True}, text='This request has expired.'), 'expired')
