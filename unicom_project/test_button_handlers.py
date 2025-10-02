# Simple test handlers for button callbacks - isolated from LLM/tools
from django.dispatch import receiver
from unicom.signals import telegram_callback_received

@receiver(telegram_callback_received)
def handle_test_buttons(sender, callback_execution, clicking_account, original_message, tool_call, **kwargs):
    """
    Test handler for button callbacks.
    Demonstrates routing and handling patterns.

    Args:
        callback_execution: The CallbackExecution instance with callback_data
        clicking_account: The Account that clicked the button
        original_message: The Message containing the buttons
        tool_call: Optional ToolCall if button was from a tool (can be None)
    """
    button_data = callback_execution.callback_data

    if not isinstance(button_data, dict):
        return

    # Get button type for routing
    button_type = button_data.get('type')
    username = clicking_account.raw.get('username', clicking_account.name)

    print(f"🧪 BUTTON CLICKED: type={button_type}, user={username}")
    if tool_call:
        print(f"   - Linked to ToolCall: {tool_call.tool_name}:{tool_call.call_id}")

    # Route based on type
    if button_type == 'test':
        handle_test_type_buttons(button_data, clicking_account, original_message, tool_call)
    elif button_type == 'product_handler':
        handle_product_type_buttons(button_data, clicking_account, original_message)
    elif button_type == 'settings_handler':
        handle_settings_type_buttons(button_data, clicking_account, original_message)
    elif button_type == 'nav_handler':
        handle_nav_type_buttons(button_data, clicking_account, original_message)
    elif button_type == 'tool_handler':
        handle_tool_type_buttons(button_data, clicking_account, original_message, tool_call)

def handle_test_type_buttons(data, account, message, tool_call):
    """Handle test-type buttons"""
    action = data.get('action')

    if action == 'basic_confirm':
        message.reply_with({'text': '✅ Basic confirm clicked! No tool_call involved.'})

    elif action == 'skip':
        message.reply_with({'text': '⏭️ Skipped! (This button has no tool_call link)'})

    elif action == 'counter':
        count = data.get('count', 0) + 1
        from unicom.services.telegram.create_inline_keyboard import create_inline_keyboard, create_callback_button

        message.edit_original_message({
            "text": f"🧪 **Test 4: Stateful Counter**\n\nCount: {count}\n\nClick to increment!",
            "reply_markup": create_inline_keyboard([
                [create_callback_button(
                    f"🔢 Count: {count}",
                    {"type": "test", "action": "counter", "count": count},
                    message=message,
                    account=account
                )],
                [create_callback_button(
                    "🔄 Reset",
                    {"type": "test", "action": "reset_counter"},
                    message=message,
                    account=account
                )]
            ])
        })

    elif action == 'reset_counter':
        from unicom.services.telegram.create_inline_keyboard import create_inline_keyboard, create_callback_button

        message.edit_original_message({
            "text": "🧪 **Test 4: Stateful Counter**\n\nCount: 0\n\nClick to increment!",
            "reply_markup": create_inline_keyboard([
                [create_callback_button(
                    "🔢 Count: 0",
                    {"type": "test", "action": "counter", "count": 0},
                    message=message,
                    account=account
                )],
                [create_callback_button(
                    "🔄 Reset",
                    {"type": "test", "action": "reset_counter"},
                    message=message,
                    account=account
                )]
            ])
        })

    elif action == 'log_click':
        message.reply_with({'text': '🧪 Test type button clicked and logged!'})

    # Legacy test types from old handler
    elif action == 'edit':
        message.edit_original_message({
            "text": "✅ Edit test successful!\n\nYou clicked the 'Edit Message' button.\nThis message was edited in place.",
            "reply_markup": None
        })

    elif action == 'reply':
        message.reply_with({
            "text": "✅ Reply test successful!\n\nYou clicked the 'Send Reply' button.\nThis is a new message."
        })

def handle_product_type_buttons(data, account, message):
    """Handle product-type buttons"""
    action = data.get('action')

    if action == 'buy':
        product_id = data.get('product_id')
        message.reply_with({'text': f'🛒 Product handler activated!\n\nProcessing purchase for product {product_id}'})

    elif action == 'view':
        product_id = data.get('product_id')
        message.reply_with({'text': f'👀 Viewing product {product_id}'})

def handle_settings_type_buttons(data, account, message):
    """Handle settings-type buttons"""
    action = data.get('action')

    if action == 'show_settings':
        message.reply_with({'text': '⚙️ Settings handler activated!\n\nShowing settings menu...'})

    elif action == 'show_privacy':
        message.reply_with({'text': '🔒 Privacy settings displayed'})

def handle_nav_type_buttons(data, account, message):
    """Handle navigation-type buttons"""
    action = data.get('action')

    if action == 'go_home':
        message.reply_with({'text': '🏠 Navigation handler activated!\n\nGoing to home...'})

def handle_tool_type_buttons(data, account, message, tool_call):
    """Handle tool-type buttons"""
    action = data.get('action')
    tool_name = data.get('tool')

    if action == 'answer' and tool_name == 'test_interactive_tool':
        answer = data.get('value')

        # Send confirmation to user
        message.reply_with({'text': f'✅ Tool handler activated!\n\nYou answered: {answer}'})

        # If there's a tool_call, respond to it
        if tool_call:
            print(f"   📤 Responding to ToolCall: {tool_call.call_id}")
            result = {
                'question_answered': True,
                'answer': answer,
                'user_id': account.id,
                'username': account.raw.get('username', account.name)
            }
            tool_call.respond(result)
            message.reply_with({'text': f'🤖 Also notified the LLM: {result}'})
        else:
            message.reply_with({'text': '⚠️ No tool_call found - button was not linked to a tool'})

    elif action == 'execute':
        message.reply_with({'text': f'🔧 Executing tool: {tool_name}'})
