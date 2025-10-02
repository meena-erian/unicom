#!/usr/bin/env python
"""Comprehensive button callback tests"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unicom_project.settings')
django.setup()

from unicom.models import Account, Message, ToolCall, Request
from unicom.services.telegram.create_inline_keyboard import (
    create_inline_keyboard, create_callback_button
)

def test_basic_buttons():
    """Test 1: Basic buttons without tool_call"""
    print("\n" + "="*60)
    print("TEST 1: Basic Buttons (No ToolCall)")
    print("="*60)

    account = Account.objects.filter(platform='Telegram').first()
    if not account:
        print("❌ No Telegram account found!")
        return False

    recent_msg = Message.objects.filter(
        sender=account,
        channel__platform='Telegram'
    ).order_by('-timestamp').first()

    if not recent_msg:
        print("❌ No recent message found!")
        return False

    # Send message with basic buttons
    recent_msg.reply_with({
        "text": "🧪 **Test 1: Basic Buttons**\n\nThese buttons have NO tool_call link:",
        "reply_markup": create_inline_keyboard([
            [create_callback_button(
                "✅ Simple Confirm",
                {"type": "test", "action": "basic_confirm"},
                message=recent_msg,
                account=account
            )],
            [create_callback_button(
                "📦 Product Test",
                {"type": "product_handler", "action": "buy", "product_id": 999},
                message=recent_msg,
                account=account
            )],
            [create_callback_button(
                "⚙️ Settings",
                {"type": "settings_handler", "action": "show_settings"},
                message=recent_msg,
                account=account
            )]
        ])
    })

    print(f"✅ Sent basic button test to {account.name}")
    print("   - 3 buttons with different types")
    print("   - No tool_call links")
    return True

def test_tool_buttons():
    """Test 2: Buttons with tool_call integration"""
    print("\n" + "="*60)
    print("TEST 2: Tool-Linked Buttons")
    print("="*60)

    account = Account.objects.filter(platform='Telegram').first()
    if not account:
        print("❌ No Telegram account found!")
        return False

    recent_msg = Message.objects.filter(
        sender=account,
        channel__platform='Telegram'
    ).order_by('-timestamp').first()

    if not recent_msg:
        print("❌ No recent message found!")
        return False

    # Create a mock ToolCall for testing
    # First we need a Request
    from django.utils import timezone

    request = Request.objects.filter(account=account).order_by('-created_at').first()
    if not request:
        print("⚠️  No existing request found, creating one...")
        request = Request.objects.create(
            message=recent_msg,
            account=account,
            channel=recent_msg.channel,
            display_text="Test request for tool buttons",
            status='PENDING'
        )

    # Create a tool_call message first
    tool_call_msg = recent_msg.log_tool_interaction(
        tool_call={
            "name": "test_interactive_tool",
            "arguments": {"question": "Do you want to proceed?"},
            "id": "test_interactive_tool_001"
        }
    )

    # Now create the ToolCall object
    tool_call = ToolCall.objects.create(
        call_id="test_interactive_tool_001",
        tool_name="test_interactive_tool",
        arguments={"question": "Do you want to proceed?"},
        status='PENDING',
        request=request,
        tool_call_message=tool_call_msg,
        initial_user_message=recent_msg
    )

    print(f"✅ Created test ToolCall: {tool_call.call_id}")

    # Send message with tool-linked buttons
    recent_msg.reply_with({
        "text": "🧪 **Test 2: Tool-Linked Buttons**\n\n"
               "These buttons are linked to a ToolCall.\n"
               f"ToolCall ID: {tool_call.call_id}\n\n"
               "When you click, the handler can respond to the tool!",
        "reply_markup": create_inline_keyboard([
            [create_callback_button(
                "✅ Yes (Tool Response)",
                {"type": "tool_handler", "tool": "test_interactive_tool", "action": "answer", "value": "yes"},
                message=recent_msg,
                account=account,
                tool_call=tool_call  # Link to tool call
            )],
            [create_callback_button(
                "❌ No (Tool Response)",
                {"type": "tool_handler", "tool": "test_interactive_tool", "action": "answer", "value": "no"},
                message=recent_msg,
                account=account,
                tool_call=tool_call  # Link to tool call
            )],
            [create_callback_button(
                "⏭️ Skip (No Response)",
                {"type": "test", "action": "skip"},
                message=recent_msg,
                account=account
                # Note: No tool_call link on this one
            )]
        ])
    })

    print(f"✅ Sent tool-linked button test")
    print(f"   - ToolCall: {tool_call.tool_name}:{tool_call.call_id}")
    print(f"   - 2 buttons linked to tool_call")
    print(f"   - 1 button without tool_call link")
    return True

def test_mixed_routing():
    """Test 3: Mixed button types for routing"""
    print("\n" + "="*60)
    print("TEST 3: Mixed Button Types (Routing Test)")
    print("="*60)

    account = Account.objects.filter(platform='Telegram').first()
    if not account:
        print("❌ No Telegram account found!")
        return False

    recent_msg = Message.objects.filter(
        sender=account,
        channel__platform='Telegram'
    ).order_by('-timestamp').first()

    if not recent_msg:
        print("❌ No recent message found!")
        return False

    # Send message with various button types
    recent_msg.reply_with({
        "text": "🧪 **Test 3: Routing Test**\n\n"
               "Each button has a different 'type' field.\n"
               "Handler should route to correct function:",
        "reply_markup": create_inline_keyboard([
            [create_callback_button(
                "🛒 Product Handler",
                {"type": "product_handler", "action": "view", "product_id": 123},
                message=recent_msg,
                account=account
            )],
            [create_callback_button(
                "🧭 Navigation Handler",
                {"type": "nav_handler", "action": "go_home"},
                message=recent_msg,
                account=account
            )],
            [create_callback_button(
                "⚙️ Settings Handler",
                {"type": "settings_handler", "action": "show_privacy"},
                message=recent_msg,
                account=account
            )],
            [create_callback_button(
                "🔧 Tool Handler",
                {"type": "tool_handler", "tool": "example_tool", "action": "execute"},
                message=recent_msg,
                account=account
            )],
            [create_callback_button(
                "🧪 Test Handler",
                {"type": "test", "action": "log_click"},
                message=recent_msg,
                account=account
            )]
        ])
    })

    print(f"✅ Sent routing test with 5 different button types")
    print("   - product_handler")
    print("   - nav_handler")
    print("   - settings_handler")
    print("   - tool_handler")
    print("   - test")
    return True

def test_counter_stateful():
    """Test 4: Stateful buttons (counter)"""
    print("\n" + "="*60)
    print("TEST 4: Stateful Buttons (Counter)")
    print("="*60)

    account = Account.objects.filter(platform='Telegram').first()
    if not account:
        print("❌ No Telegram account found!")
        return False

    recent_msg = Message.objects.filter(
        sender=account,
        channel__platform='Telegram'
    ).order_by('-timestamp').first()

    if not recent_msg:
        print("❌ No recent message found!")
        return False

    # Send message with counter button
    recent_msg.reply_with({
        "text": "🧪 **Test 4: Stateful Counter**\n\n"
               "Count: 0\n\n"
               "Click to increment!",
        "reply_markup": create_inline_keyboard([
            [create_callback_button(
                "🔢 Count: 0",
                {"type": "test", "action": "counter", "count": 0},
                message=recent_msg,
                account=account
            )],
            [create_callback_button(
                "🔄 Reset",
                {"type": "test", "action": "reset_counter"},
                message=recent_msg,
                account=account
            )]
        ])
    })

    print(f"✅ Sent stateful counter test")
    print("   - Counter starts at 0")
    print("   - Handler should increment on click")
    return True

def run_all_tests():
    """Run all button tests"""
    print("\n" + "="*70)
    print("  COMPREHENSIVE BUTTON CALLBACK TESTS")
    print("="*70)

    account = Account.objects.filter(platform='Telegram').first()
    if account:
        print(f"\n📱 Testing with account: {account.name} ({account.id})")

    tests = [
        ("Basic Buttons", test_basic_buttons),
        ("Tool-Linked Buttons", test_tool_buttons),
        ("Mixed Routing", test_mixed_routing),
        ("Stateful Counter", test_counter_stateful)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} FAILED with exception:")
            print(f"   {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests completed successfully!")
        print("\n📝 Now try clicking the buttons in Telegram to verify handlers work!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

    return passed == total

if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
