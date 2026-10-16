# Tool interactions and custom web presentations

UniCom persists a tool's user prompt and exposes the same actions through WebChat
and Telegram. WebChat can render a trusted custom Web Component; Telegram shows
text and inline buttons. The tool response is deferred until a choice or expiry.
Apply migration `0027_interaction` before using this API.

## Public Python API

```python
from unicom.interactions import Button, MessageWithButtons
from unicom.services.interactions import start_interaction

prompt = MessageWithButtons(
    text='Which format would you like?',
    buttons=[Button('PDF', 'pdf'), Button('CSV', 'csv', 'secondary')],
    presentation={'formats': ['pdf', 'csv']},
    expires_in=3600,
)
# Inside a tool executor, using the persisted UniCom ToolCall:
start_interaction(prompt, tool_call)
# Do not call tool_call.respond() here; the interaction completes it later.
```

The base class completes with `{'action': selected_action}`. For custom behavior,
subclass `MessageWithButtons` and implement `on_action(action, context)`. Return
`Complete(result, text=..., presentation=..., cancelled=False)` to finish, or
another registered `MessageWithButtons` for a further step. Cancellation is an
explicit completion flag; an action named `cancel` alone has no special behavior.
Further steps retain the original expiration deadline.

`self.state` is private persisted JSON. `self.presentation` is public JSON.
`context` exposes `interaction`, `account`, `tool_call`, and the original Django
`user` (which may be absent for guests). Recheck domain-specific permissions in
handlers. Do not depend on initial tool globals or in-memory closures surviving.

Register custom classes with a stable resolver at application startup:

```python
from unicom.interactions import Complete, register_interaction_resolver

class PickFormat(MessageWithButtons):
    handler_key = 'reports:PickFormat'

    def on_action(self, action, context):
        return Complete({'format': action}, text=f'Selected {action}',
                        presentation={'format': action})

handlers = {'PickFormat': PickFormat}
register_interaction_resolver('reports', lambda name: handlers[name])
```

Keep resolver keys available while saved interactions are pending. UniBot handles
this registration automatically for a tool definition's `interactions` mapping;
see its `TOOL_INTERACTIONS.md` for definition-local Python and JavaScript examples.

Prompt text must contain 1–3500 characters. Supply 1–20 unique actions, with
labels and action names of 1–64 characters. Button styles are `primary`,
`secondary`, or `danger`. State, presentation and completion results must be
JSON-serializable. Expiry defaults to one hour and accepts 1 second through 7 days.

## Custom web component

Set the handler class's `web_component` to `{'module': same_origin_static_url}`.
Resolve that URL using Django static storage when configuring the handler so
manifest storage can supply a versioned asset. UniBot also supports a companion
`<tool_name>.presentation.js` string through its definition loader and finder.

The JavaScript module exports a standard Web Component class:

```javascript
export default class FormatCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: 'open'});
  }
  set state(state) {
    const title = document.createElement('h3');
    title.textContent = state.text;
    const summary = document.createElement('p');
    summary.textContent = state.status === 'awaiting_input'
      ? 'Select a format below.'
      : `Selected format: ${state.data.format || 'none'}`;
    this.shadowRoot.replaceChildren(title, summary);
  }
}
```

UniCom registers and mounts the component. `.state` contains:

```javascript
{
  id, callId, toolName, status, revision, text,
  data,          // only explicit presentation data
  component, buttons, expiresAt
}
```

States are `awaiting_input`, `completed`, `cancelled`, `expired`, and `error`.
Use `data` for previews and final visualizations; set the completion's
`presentation` to the data the final view needs. Render with DOM text APIs or
escaped templates, not interpolated untrusted HTML. Modules are trusted deployed
application code and must be same-origin. They may use SVG, icons, charts, shadow
DOM, and the inherited `--unicom-*` theme variables. The host supplies accessible
buttons, busy state, CSRF-protected submission, and visible errors. A custom
component can also emit a bubbling, composed `interaction-action` event with
`detail: {action: 'pdf'}` to activate an existing declared action. It cannot add
new server actions by changing client data.

Implement `disconnectedCallback` to release listeners, timers, and in-flight
work. State may be assigned repeatedly as messages refresh. Preserve your own
component-local state where appropriate. If loading the module fails, UniCom
falls back to the text and standard buttons. Telegram always uses that textual
contract, so provide useful `text` for every step and completion.

The initial card appears after the Python tool returns its interaction object,
while the model's tool response is still pending. It is not a hook that renders
before `run()` returns. Pass selected tool arguments into `presentation` for a
data-driven preview; return final display data through `Complete.presentation`.
The existing component receives the new `.state` when the interaction updates.

## Lifecycle and guarantees

The interaction's private state, public data, identity, buttons, revision, result,
and expiration live in the database. Web history reconstructs the card; guest
interactions transfer with chat history at sign-in. Account ownership and channel
are checked for callbacks. CSRF remains enforced on web submissions.

Clicks lock the interaction's parent request and interaction rows. Duplicate or
concurrent clicks on a completed interaction return the saved state and cannot
roll the dice or create another continuation. Sibling pending tools block the
continuation until all have responded. Exceptions roll back database changes and
leave the interaction available for retry. External side effects cannot be
rolled back by Django: use an outbox or the interaction ID as the external
provider's idempotency key, and keep handlers short.

Interactions default to a one-hour deadline; `expires_in` accepts 1 second through
7 days. The UniBot worker checks for expired interactions approximately every
30 seconds between processing batches. Standalone UniCom integrations can run
`python manage.py expire_interactions` periodically. Expiry resolves the tool
with an error result. Telegram projection is best-effort: provider outages can
leave old buttons visible, but those buttons cannot repeat a completed action.

Standalone executors call `start_interaction(prompt, tool_call)` and defer their
normal response. UniBot/custom UniBot adapters can use
`handle_interaction_result(value, tool_call)` from `unibot.interactions` and skip
ordinary completion when it returns `True`.

## Current scope

Supported: buttons, multiple button-driven steps, custom web previews and final
views, persisted history, and text/button Telegram projection. Typed form
submission, file uploads, Telegram conversational forms, and streaming
intermediate tool data are not implemented by this API. Web-only controls do not
automatically translate into Telegram input flows.
