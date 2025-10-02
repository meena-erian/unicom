# Interactive menu tool - demonstrates Telegram button functionality
from unicom.services.telegram.create_inline_keyboard import (
    create_inline_keyboard, create_callback_button, create_url_button, create_simple_keyboard
)

def interactive_menu(menu_type: str = "main") -> str:
    """
    Display an interactive menu with buttons for different actions.

    Args:
        menu_type: Type of menu to display ("main", "tools", "info")

    Returns:
        String confirmation that menu was sent
    """
    try:
        # message is available directly as a context variable in tool code
        if menu_type == "main":
            # Main menu with different options
            buttons = create_inline_keyboard([
                [create_callback_button("🛠️ Tools Menu", "menu_tools")],
                [create_callback_button("ℹ️ System Info", "menu_info")],
                [create_callback_button("🎲 Random Fact", "action_random_fact")],
                [create_url_button("📖 Documentation", "https://github.com/meena-erian/unicom")]
            ])

            # Send the menu directly using message.reply_with
            if message:
                message.reply_with({
                    "text": "🏠 **Main Menu**\n\nChoose an option below:",
                    "reply_markup": buttons
                })
                return "Interactive main menu sent with buttons!"
            else:
                return "🏠 **Main Menu**\n\nChoose an option below:"

        elif menu_type == "tools":
            # Tools submenu
            buttons = create_inline_keyboard([
                [create_callback_button("⏰ Start Timer", "action_timer")],
                [create_callback_button("🌐 IP Lookup", "action_ip_lookup")],
                [create_callback_button("📊 System Stats", "action_system_info")],
                [create_callback_button("🔙 Back to Main", "menu_main")]
            ])

            if message:
                message.reply_with({
                    "text": "🛠️ **Tools Menu**\n\nSelect a tool to use:",
                    "reply_markup": buttons
                })
                return "Tools menu sent with buttons!"
            else:
                return "🛠️ **Tools Menu**\n\nSelect a tool to use:"

        elif menu_type == "info":
            # Info submenu
            buttons = create_inline_keyboard([
                [create_callback_button("💻 System Info", "action_system_info")],
                [create_callback_button("📈 Performance", "action_performance")],
                [create_callback_button("🔙 Back to Main", "menu_main")]
            ])

            if message:
                message.reply_with({
                    "text": "ℹ️ **Information Menu**\n\nWhat would you like to know?",
                    "reply_markup": buttons
                })
                return "Info menu sent with buttons!"
            else:
                return "ℹ️ **Information Menu**\n\nWhat would you like to know?"

        else:
            if message:
                message.reply_with({
                    "text": f"Unknown menu type: {menu_type}",
                    "reply_markup": create_simple_keyboard("🏠 Main Menu", "menu_main")
                })
                return f"Unknown menu type: {menu_type} (sent error with menu button)"
            else:
                return f"Unknown menu type: {menu_type}"

    except Exception as e:
        if message:
            message.reply_with({
                "text": f"Menu error: {str(e)}",
                "reply_markup": create_simple_keyboard("🏠 Try Main Menu", "menu_main")
            })
            return f"Menu error occurred: {str(e)} (sent error message with menu button)"
        else:
            return f"Menu error: {str(e)}"

tool_definition = {
    "name": "interactive_menu",
    "description": "Display an interactive menu with clickable buttons for various actions",
    "parameters": {
        "menu_type": {
            "type": "string",
            "description": "Type of menu to display",
            "enum": ["main", "tools", "info"],
            "default": "main"
        }
    },
    "run": interactive_menu
}