# Cross-platform button test tool
def cross_platform_buttons(button_type: str = "basic") -> str:
    """
    Test cross-platform interactive buttons that work on both Telegram and WebChat.

    Args:
        button_type: Type of buttons to display ("basic", "advanced", "mixed")

    Returns:
        None to prevent duplicate messages
    """
    try:
        if not message:
            return "Message context not available"

        if button_type == "basic":
            message.reply_with({
                "text": "🧪 **Cross-Platform Button Test**\n\nThese buttons work on both Telegram and WebChat:",
                "buttons": [
                    [
                        {"text": "✅ Confirm", "callback_data": {"action": "confirm", "test": "basic"}, "type": "callback"},
                        {"text": "❌ Cancel", "callback_data": {"action": "cancel", "test": "basic"}, "type": "callback"}
                    ],
                    [
                        {"text": "ℹ️ Info", "callback_data": {"action": "info", "test": "basic"}, "type": "callback"}
                    ]
                ]
            })
            return None

        elif button_type == "advanced":
            message.reply_with({
                "text": "🚀 **Advanced Button Test**\n\nButtons with complex data:",
                "buttons": [
                    [
                        {"text": "📦 Product A", "callback_data": {"action": "buy", "product_id": 123, "price": 29.99}, "type": "callback"},
                        {"text": "📦 Product B", "callback_data": {"action": "buy", "product_id": 456, "price": 49.99}, "type": "callback"}
                    ],
                    [
                        {"text": "🛒 View Cart", "callback_data": {"action": "view_cart", "user_id": "test_user"}, "type": "callback"}
                    ]
                ]
            })
            return None

        elif button_type == "mixed":
            message.reply_with({
                "text": "🌐 **Mixed Button Test**\n\nCallback buttons + URL buttons:",
                "buttons": [
                    [
                        {"text": "🔗 Visit GitHub", "url": "https://github.com/meena-erian/unicom", "type": "url"},
                        {"text": "📚 Documentation", "url": "https://example.com/docs", "type": "url"}
                    ],
                    [
                        {"text": "⚙️ Settings", "callback_data": {"action": "settings", "page": "main"}, "type": "callback"},
                        {"text": "❓ Help", "callback_data": {"action": "help", "topic": "buttons"}, "type": "callback"}
                    ]
                ]
            })
            return None

        else:
            message.reply_with({
                "text": f"Unknown button type: {button_type}",
                "buttons": [
                    [
                        {"text": "🔄 Try Again", "callback_data": {"action": "retry", "original_type": button_type}, "type": "callback"}
                    ]
                ]
            })
            return None

    except Exception as e:
        import traceback
        traceback.print_exc()
        if message:
            message.reply_with({"text": f"Button test error: {str(e)}"})
        return f"Button test error: {str(e)}"

tool_definition = {
    "name": "cross_platform_buttons",
    "description": "Test cross-platform interactive buttons that work on both Telegram and WebChat",
    "parameters": {
        "button_type": {
            "type": "string",
            "description": "Type of buttons to display",
            "enum": ["basic", "advanced", "mixed"],
            "default": "basic"
        }
    },
    "run": cross_platform_buttons
}
