# Callback handlers for interactive menu buttons
from django.dispatch import receiver
from unicom.signals import telegram_callback_received
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
def handle_interactive_menu_buttons(sender, callback_execution, callback_message, **kwargs):
    """
    Handle button clicks from the interactive menu tool.
    """
    button_data = callback_execution.callback_data
    account = callback_execution.intended_account
    callback_msg = callback_message
    original_msg = callback_execution.original_message

    username = account.raw.get('username', account.name)
    print(f"🎯 HANDLER DEBUG: Button clicked: {button_data} by {username}")
    print(f"   - Callback Message ID: {callback_msg.id}")
    print(f"   - Original Message ID: {original_msg.id}")
    print(f"   - Account: {username} ({account.id})")

    # Handle menu navigation
    if button_data == "menu_main":
        show_main_menu(callback_msg)

    elif button_data == "menu_tools":
        show_tools_menu(callback_msg)

    elif button_data == "menu_info":
        print(f"🔧 HANDLER DEBUG: Calling show_info_menu")
        try:
            show_info_menu(callback_msg)
            print(f"✅ HANDLER DEBUG: show_info_menu completed successfully")
        except Exception as e:
            print(f"❌ HANDLER DEBUG: Error in show_info_menu: {str(e)}")
            import traceback
            traceback.print_exc()

    # Handle actions
    elif button_data == "action_random_fact":
        show_random_fact(callback_msg)

    elif button_data == "action_timer":
        start_timer_demo(callback_msg)

    elif button_data == "action_ip_lookup":
        show_ip_lookup_demo(callback_msg)

    elif button_data == "action_system_info":
        show_system_info(callback_msg)

    elif button_data == "action_performance":
        show_performance_info(callback_msg)

    elif button_data.startswith("timer_"):
        # Handle timer buttons (e.g., "timer_10", "timer_30")
        seconds = int(button_data.split("_")[1])
        start_actual_timer(callback_msg, seconds)

    else:
        # Unknown button
        callback_msg.reply_with({
            'text': f'🤔 Unknown action: {button_data}',
            'reply_markup': create_simple_keyboard("🏠 Main Menu", "menu_main")
        })

def show_main_menu(message):
    """Show the main menu"""
    buttons = create_inline_keyboard([
        [create_callback_button("🛠️ Tools Menu", "menu_tools")],
        [create_callback_button("ℹ️ System Info", "menu_info")],
        [create_callback_button("🎲 Random Fact", "action_random_fact")],
        [create_url_button("📖 Documentation", "https://github.com/meena-erian/unicom")]
    ])

    message.edit_original_message({
        "text": "🏠 **Main Menu**\n\nChoose an option below:",
        "reply_markup": buttons
    })

def show_tools_menu(message):
    """Show the tools submenu"""
    buttons = create_inline_keyboard([
        [create_callback_button("⏰ Start Timer", "action_timer")],
        [create_callback_button("🌐 IP Lookup", "action_ip_lookup")],
        [create_callback_button("📊 System Stats", "action_system_info")],
        [create_callback_button("🔙 Back to Main", "menu_main")]
    ])

    message.edit_original_message({
        "text": "🛠️ **Tools Menu**\n\nSelect a tool to use:",
        "reply_markup": buttons
    })

def show_info_menu(message):
    """Show the info submenu"""
    print(f"🔧 MENU DEBUG: Creating info menu buttons")
    buttons = create_inline_keyboard([
        [create_callback_button("💻 System Info", "action_system_info")],
        [create_callback_button("📈 Performance", "action_performance")],
        [create_callback_button("🔙 Back to Main", "menu_main")]
    ])
    print(f"✅ MENU DEBUG: Buttons created: {buttons}")

    print(f"🔧 MENU DEBUG: Calling edit_original_message")
    result = message.edit_original_message({
        "text": "ℹ️ **Information Menu**\n\nWhat would you like to know?",
        "reply_markup": buttons
    })
    print(f"✅ MENU DEBUG: edit_original_message result: {result}")

def show_random_fact(message):
    """Show a random fact"""
    fact = random.choice(RANDOM_FACTS)

    message.reply_with({
        'text': f"🎲 **Random Fact**\n\n{fact}",
        'reply_markup': create_inline_keyboard([
            [create_callback_button("🎲 Another Fact", "action_random_fact")],
            [create_callback_button("🏠 Main Menu", "menu_main")]
        ])
    })

def start_timer_demo(message):
    """Show timer options"""
    buttons = create_inline_keyboard([
        [create_callback_button("⏰ 10 seconds", "timer_10"), create_callback_button("⏰ 30 seconds", "timer_30")],
        [create_callback_button("⏰ 60 seconds", "timer_60")],
        [create_callback_button("🔙 Back to Tools", "menu_tools")]
    ])

    message.edit_original_message({
        "text": "⏰ **Timer Demo**\n\nChoose how long to wait:",
        "reply_markup": buttons
    })

def start_actual_timer(message, seconds):
    """Start an actual timer"""
    message.reply_with({
        'text': f"⏰ Starting {seconds}-second timer..."
    })

    # Use the existing simple_timer tool
    import time
    time.sleep(seconds)

    message.reply_with({
        'text': f"🔔 Timer finished! Waited {seconds} seconds.",
        'reply_markup': create_simple_keyboard("🏠 Main Menu", "menu_main")
    })

def show_ip_lookup_demo(message):
    """Show IP lookup info"""
    message.edit_original_message({
        "text": "🌐 **IP Lookup Demo**\n\nThis would normally do an IP lookup.\nFor the demo, we'll just show this message!",
        "reply_markup": create_inline_keyboard([
            [create_callback_button("🔙 Back to Tools", "menu_tools")],
            [create_callback_button("🏠 Main Menu", "menu_main")]
        ])
    })

def show_system_info(message):
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

    message.reply_with({
        'text': system_info,
        'reply_markup': create_inline_keyboard([
            [create_callback_button("📈 Performance", "action_performance")],
            [create_callback_button("🔙 Back to Info", "menu_info")]
        ])
    })

def show_performance_info(message):
    """Show performance information"""
    try:
        # Simple performance info without psutil
        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else ('N/A', 'N/A', 'N/A')

        performance_info = f"""📈 **Performance Information**

🔥 **Load Average**: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}
💾 **Process ID**: {os.getpid()}
🖥️ **CPU Count**: {os.cpu_count() or 'Unknown'}
📁 **Current Directory**: {os.getcwd()}
"""
    except Exception as e:
        performance_info = f"❌ Error getting performance info: {str(e)}"

    message.reply_with({
        'text': performance_info,
        'reply_markup': create_inline_keyboard([
            [create_callback_button("💻 System Info", "action_system_info")],
            [create_callback_button("🔙 Back to Info", "menu_info")]
        ])
    })