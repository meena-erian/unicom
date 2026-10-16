"""Public, transport-independent API for persisted tool interactions.

Handlers must be deterministic/transactional; external side effects should use
an outbox or the interaction ID as their provider idempotency key.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Button:
    text: str
    action: str
    style: str = "primary"


@dataclass
class Complete:
    result: object
    text: str = "Completed"
    presentation: dict = field(default_factory=dict)
    cancelled: bool = False


@dataclass(frozen=True)
class InteractionContext:
    interaction: object
    account: object
    tool_call: object

    @property
    def user(self):
        return self.tool_call.initial_user_message.user


class MessageWithButtons:
    """Subclass on_action, or use directly for a simple choice tool.

    state is private JSON for the handler. presentation is deliberately public
    JSON for the web component. Neither is supplied by the model implicitly.
    """
    text = "Choose an option"
    buttons = ()
    handler_key = "unicom:choice"
    web_component = None

    def __init__(self, *, text=None, buttons=None, state=None, presentation=None, expires_in=3600):
        self.text = text if text is not None else type(self).text
        self.buttons = buttons if buttons is not None else type(self).buttons
        self.state = state or {}
        self.presentation = presentation or {}
        self.expires_in = expires_in

    def on_action(self, action, context):
        return Complete({"action": action}, text=f"Selected: {action}")


_resolvers = {}


def register_interaction_resolver(namespace, resolver):
    """Register trusted server code that resolves persisted handler identifiers."""
    _resolvers[namespace] = resolver


def resolve_handler(key):
    if key == "unicom:choice":
        return MessageWithButtons
    namespace, identifier = key.split(":", 1)
    return _resolvers[namespace](identifier)
