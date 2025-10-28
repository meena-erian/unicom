# Assistant bot with testing tools
# List of tools this bot can use
bot_tools = ["get_system_info", "simple_timer", "interval_alarm", "ip_lookup", "cross_platform_buttons"]

def handle_incoming_message(message, bot, tools_list):
    """Handle incoming messages for the assistant bot"""
    return bot.reply_using_llm(
        message,
        tools_list,
        system_instruction="""You are a helpful assistant with system utilities.""",
        request=request
    )