"""Project-neutral chat handoff state and request gating.

The feature is opt-in: chats without a handoff marker retain the historical
automated-processing behaviour.
"""

from django.db import transaction


AUTOMATION_MODE_KEY = "automation_mode"
BOT_MODE = "bot"
HUMAN_MODE = "human"


def chat_automation_mode(chat):
    return (chat.metadata or {}).get(AUTOMATION_MODE_KEY, BOT_MODE)


def chat_allows_automation(chat):
    return chat_automation_mode(chat) == BOT_MODE


@transaction.atomic
def handoff_chat(chat, *, metadata=None):
    """Put a chat into human mode and return the refreshed chat.

    Existing callers are unaffected because the default mode is ``bot``.
    """
    locked = type(chat).objects.select_for_update().get(pk=chat.pk)
    values = dict(locked.metadata or {})
    values[AUTOMATION_MODE_KEY] = HUMAN_MODE
    if metadata:
        values.update(metadata)
    locked.metadata = values
    locked.save(update_fields=["metadata"])
    return locked


@transaction.atomic
def resume_chat_automation(chat):
    locked = type(chat).objects.select_for_update().get(pk=chat.pk)
    values = dict(locked.metadata or {})
    values[AUTOMATION_MODE_KEY] = BOT_MODE
    locked.metadata = values
    locked.save(update_fields=["metadata"])
    return locked
