## Current Telegram Button System Analysis

The Telegram button system has these key components:

1. Button Creation: create_callback_button() creates buttons with JSON-serializable callback data
2. Storage: CallbackExecution model stores button metadata and links to original message/account/tool_call
3. Processing: handle_telegram_callback() processes clicks and fires Django signals
4. Handlers: Developers write signal receivers to handle button clicks with custom logic
5. Security: Only intended accounts can click buttons, with expiration support

## Suggested Cross-Platform Extension for WebChat

### 1. Abstract Button System Architecture

python
# New abstract service layer
unicom/services/crossplatform/interactive_buttons.py

class InteractiveButton:
    def __init__(self, text, callback_data, button_type='callback', **kwargs):
        self.text = text
        self.callback_data = callback_data
        self.button_type = button_type  # 'callback', 'url', 'action'
        self.metadata = kwargs

def create_platform_buttons(buttons, message=None, account=None, tool_call=None):
    """Platform-agnostic button creation"""
    if message.platform == 'Telegram':
        return create_telegram_buttons(buttons, message, account, tool_call)
    elif message.platform == 'WebChat':
        return create_webchat_buttons(buttons, message, account, tool_call)
    # Future: WhatsApp, Email, etc.


### 2. WebChat Button Implementation

python
# Extend Message model to support buttons
class Message(models.Model):
    # ... existing fields ...
    interactive_buttons = models.JSONField(null=True, blank=True, 
                                         help_text="Platform-agnostic button data")

# WebChat button rendering in message-item.js
_renderInteractiveButtons(buttons) {
    if (!buttons || !buttons.length) return '';
    
    return html`
        <div class="interactive-buttons">
            ${buttons.map(button => html`
                <button 
                    class="interactive-btn ${button.style || 'primary'}"
                    @click=${() => this._handleButtonClick(button)}
                    ?disabled=${button.disabled}>
                    ${button.text}
                </button>
            `)}
        </div>
    `;
}


### 3. Unified Signal System

python
# Extend existing signals for cross-platform support
interactive_button_clicked = Signal()  # New cross-platform signal

@receiver(interactive_button_clicked)
def handle_button_clicks(sender, callback_execution, clicking_account, original_message, platform, **kwargs):
    """Universal button handler - works for all platforms"""
    data = callback_execution.callback_data
    
    # Same handler logic works for Telegram, WebChat, etc.
    if data.get('action') == 'confirm':
        process_confirmation(clicking_account, original_message)


### 4. WebChat API Extension

python
# New endpoint for button clicks
@csrf_exempt
@require_http_methods(["POST"])
def handle_webchat_button_click(request):
    """Handle WebChat button clicks - mirrors Telegram callback system"""
    callback_execution_id = request.POST.get('callback_execution_id')
    
    # Same security/validation logic as Telegram
    execution = CallbackExecution.objects.get(id=callback_execution_id)
    if execution.is_expired() or not authorized:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Fire same signal as Telegram
    interactive_button_clicked.send(
        sender=handle_webchat_button_click,
        callback_execution=execution,
        clicking_account=account,
        original_message=execution.original_message,
        platform='WebChat'
    )


### 5. Frontend WebChat Button Handling

javascript
// In message-item.js
_handleButtonClick(button) {
    // Send button click to backend
    fetch('/unicom/webchat/button-click/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            callback_execution_id: button.callback_execution_id
        })
    }).then(response => {
        if (response.ok) {
            // Refresh messages to show any updates
            this.dispatchEvent(new CustomEvent('refresh-messages'));
        }
    });
}


### 6. Unified Developer API

python
# Same API works across platforms
message.reply_with({
    'text': 'Choose an option:',
    'buttons': [  # New cross-platform field
        {'text': 'Confirm', 'callback_data': {'action': 'confirm'}},
        {'text': 'Cancel', 'callback_data': {'action': 'cancel'}},
        {'text': 'Visit Site', 'url': 'https://example.com', 'type': 'url'}
    ]
})

# Platform-specific rendering:
# - Telegram: Converts to reply_markup inline_keyboard
# - WebChat: Renders as HTML buttons
# - Email: Could render as HTML buttons or links
# - WhatsApp: Could use quick reply buttons


## Key Benefits of This Approach

1. Unified API: Same button creation code works across all platforms
2. Consistent Handlers: Same signal receivers handle clicks from any platform  
3. Security: Same CallbackExecution model provides security for all platforms
4. Extensible: Easy to add new platforms (WhatsApp, Email) later
5. Backward Compatible: Existing Telegram code continues working unchanged

## Implementation Priority for WebChat

1. Phase 1: Extend Message model with interactive_buttons field
2. Phase 2: Add WebChat button rendering in frontend components
3. Phase 3: Create WebChat button click API endpoint
4. Phase 4: Extend signal system for cross-platform support
5. Phase 5: Create unified developer API wrapper
