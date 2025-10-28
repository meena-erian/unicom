# Callback handlers for interactive menu buttons
from django.dispatch import receiver
from unicom.signals import telegram_callback_received, interactive_button_clicked
from unicom.services.telegram.create_inline_keyboard import create_simple_keyboard, create_inline_keyboard, create_callback_button, create_url_button
import random
import platform
from datetime import datetime
import os

# List of random facts for demo
RANDOM_FACTS = [
    "🐙 Octopuses have three hearts and blue blood!",
    "🌙 A day on Venus is longer than its year!",
    "🦆 Ducks can see in almost 360 degrees!",
    "🍯 Honey never spoils - archaeologists found edible honey in Egyptian tombs!",
    "🐧 Penguins can drink saltwater because they have special glands to filter salt!",
    "🌈 There are more possible chess games than atoms in the observable universe!",
    "🦈 Sharks have been around longer than trees!",
    "🧠 Your brain uses about 20% of your body's total energy!"
]

@receiver(telegram_callback_received)
def handle_interactive_menu_buttons(sender, callback_execution, clicking_account, original_message, tool_call, **kwargs):
    """Handle button clicks from Telegram"""
    handle_button_clicks(callback_execution, clicking_account, original_message, 'Telegram', tool_call)

@receiver(interactive_button_clicked)
def handle_webchat_buttons(sender, callback_execution, clicking_account, original_message, platform, tool_call, **kwargs):
    """Handle button clicks from WebChat"""
    handle_button_clicks(callback_execution, clicking_account, original_message, platform, tool_call)

def handle_button_clicks(callback_execution, clicking_account, original_message, platform, tool_call):
    """
    Unified handler for button clicks from any platform.
    """
    button_data = callback_execution.callback_data
    username = clicking_account.raw.get('username', clicking_account.name)
    
    print(f"🎯 BUTTON CLICK: {platform} button clicked: {button_data} by {username}")
    
    # Handle dict-based callback_data
    if isinstance(button_data, dict):
        action = button_data.get("action")
        
        if action == "confirm":
            test_type = button_data.get("test", "unknown")
            original_message.reply_with({
                'text': f'✅ **Confirmed!**\n\nTest: {test_type}\nPlatform: {platform}\nUser: {username}'
            })
            
        elif action == "cancel":
            test_type = button_data.get("test", "unknown")
            original_message.reply_with({
                'text': f'❌ **Cancelled**\n\nTest: {test_type}\nPlatform: {platform}\nUser: {username}'
            })
            
        elif action == "info":
            original_message.reply_with({
                'text': f'ℹ️ **Button Info**\n\n• Platform: {platform}\n• User: {username}\n• Data: {button_data}'
            })
            
        # Handle existing menu actions for backward compatibility
        elif button_data.get("menu") == "main":
            show_main_menu(original_message, clicking_account)
        elif button_data.get("menu") == "tools":
            show_tools_menu(original_message, clicking_account)
        elif button_data.get("menu") == "info":
            show_info_menu(original_message, clicking_account)
        elif button_data.get("action") == "random_fact":
            show_random_fact(original_message, clicking_account)
        elif button_data.get("action") == "timer":
            start_timer_demo(original_message, clicking_account)
        elif button_data.get("action") == "ip_lookup":
            show_ip_lookup_demo(original_message, clicking_account)
        elif button_data.get("action") == "system_info":
            show_system_info(original_message, clicking_account)
        elif button_data.get("action") == "performance":
            show_performance_info(original_message, clicking_account)
        elif button_data.get("action") == "start_timer":
            seconds = button_data.get("seconds", 10)
            start_actual_timer(original_message, clicking_account, seconds)
        else:
            original_message.reply_with({'text': f'🤔 Unknown action: {button_data}'})

    # Handle legacy string-based callback_data (for backwards compatibility)
    elif isinstance(button_data, str):
        original_message.reply_with({'text': f'Legacy button clicked: {button_data}'})

def show_main_menu(message, account):
    """Show the main menu"""
    message.edit_original_message({
        "text": "🏠 **Main Menu**\n\nChoose an option below:",
        "reply_markup": create_inline_keyboard([
            [create_callback_button("🛠️ Tools Menu", {"menu": "tools"}, message=message, account=account)],
            [create_callback_button("ℹ️ System Info", {"menu": "info"}, message=message, account=account)],
            [create_callback_button("🎲 Random Fact", {"action": "random_fact"}, message=message, account=account)],
            [create_url_button("📖 Documentation", "https://github.com/meena-erian/unicom")]
        ])
    })

def show_tools_menu(message, account):
    """Show the tools submenu"""
    message.edit_original_message({
        "text": "🛠️ **Tools Menu**\n\nSelect a tool to use:",
        "reply_markup": create_inline_keyboard([
            [create_callback_button("⏰ Start Timer", {"action": "timer"}, message=message, account=account)],
            [create_callback_button("🌐 IP Lookup", {"action": "ip_lookup"}, message=message, account=account)],
            [create_callback_button("📊 System Stats", {"action": "system_info"}, message=message, account=account)],
            [create_callback_button("🔙 Back to Main", {"menu": "main"}, message=message, account=account)]
        ])
    })

def show_info_menu(message, account):
    """Show the info submenu"""
    message.edit_original_message({
        "text": "ℹ️ **Information Menu**\n\nWhat would you like to know?",
        "reply_markup": create_inline_keyboard([
            [create_callback_button("💻 System Info", {"action": "system_info"}, message=message, account=account)],
            [create_callback_button("📈 Performance", {"action": "performance"}, message=message, account=account)],
            [create_callback_button("🔙 Back to Main", {"menu": "main"}, message=message, account=account)]
        ])
    })

def show_random_fact(message, account):
    """Show a random fact"""
    fact = random.choice(RANDOM_FACTS)
    sent_msg = message.reply_with({'text': f"🎲 **Random Fact**\n\n{fact}"})
    # Note: Can't add buttons to already-sent message easily, skip for now
    # In production, you'd send with buttons initially

def start_timer_demo(message, account):
    """Show timer options"""
    message.edit_original_message({
        "text": "⏰ **Timer Demo**\n\nChoose how long to wait:",
        "reply_markup": create_inline_keyboard([
            [create_callback_button("⏰ 10 seconds", {"action": "start_timer", "seconds": 10}, message=message, account=account)],
            [create_callback_button("⏰ 30 seconds", {"action": "start_timer", "seconds": 30}, message=message, account=account)],
            [create_callback_button("⏰ 60 seconds", {"action": "start_timer", "seconds": 60}, message=message, account=account)],
            [create_callback_button("🔙 Back to Tools", {"menu": "tools"}, message=message, account=account)]
        ])
    })

def start_actual_timer(message, account, seconds):
    """Start an actual timer"""
    message.reply_with({'text': f"⏰ Starting {seconds}-second timer..."})
    import time
    time.sleep(seconds)
    message.reply_with({'text': f"🔔 Timer finished! Waited {seconds} seconds."})

def show_ip_lookup_demo(message, account):
    """Show IP lookup info"""
    message.edit_original_message({
        "text": "🌐 **IP Lookup Demo**\n\nThis would normally do an IP lookup.\nFor the demo, we'll just show this message!",
        "reply_markup": create_inline_keyboard([
            [create_callback_button("🔙 Back to Tools", {"menu": "tools"}, message=message, account=account)],
            [create_callback_button("🏠 Main Menu", {"menu": "main"}, message=message, account=account)]
        ])
    })

def show_system_info(message, account):
    """Show basic system information"""
    try:
        system_info = f"""💻 **System Information**

🖥️ **OS**: {platform.system()} {platform.release()}
🏗️ **Architecture**: {platform.machine()}
🐍 **Python**: {platform.python_version()}
📅 **Current Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    except Exception as e:
        system_info = f"❌ Error getting system info: {str(e)}"

    sent_msg = message.reply_with({'text': system_info})

def show_performance_info(message, account):
    """Show performance information"""
    try:
        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else ('N/A', 'N/A', 'N/A')
        performance_info = f"""📈 **Performance Information**

🔥 **Load Average**: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}
💾 **Process ID**: {os.getpid()}
🖥️ **CPU Count**: {os.cpu_count() or 'Unknown'}
📁 **Current Directory**: {os.getcwd()}
"""
    except Exception as e:
        performance_info = f"❌ Error getting performance info: {str(e)}"

    message.reply_with({'text': performance_info})