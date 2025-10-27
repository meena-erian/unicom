#!/usr/bin/env python
"""
Debug script to analyze the branching logic with real data
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unicom_project.settings')
django.setup()

from unicom.models import Message

def debug_branching_logic():
    chat_id = "webchat_d5eeb4e8-b46d-41fd-b3c2-17ef8f268b7d"
    
    # Get all messages for this chat
    messages = list(Message.objects.filter(chat_id=chat_id).order_by('timestamp'))
    
    print(f"Found {len(messages)} messages in chat {chat_id}")
    print("\n=== All Messages ===")
    for msg in messages:
        print(f"ID: {msg.id}")
        print(f"  Text: {msg.text[:50]}...")
        print(f"  Reply to: {msg.reply_to_message_id}")
        print(f"  Outgoing: {msg.is_outgoing}")
        print(f"  Timestamp: {msg.timestamp}")
        print()
    
    # Find branch groups
    branch_groups = {}
    for msg in messages:
        reply_to = msg.reply_to_message_id
        if reply_to:
            if reply_to not in branch_groups:
                branch_groups[reply_to] = []
            branch_groups[reply_to].append(msg)
    
    print("=== Branch Groups ===")
    for reply_to, group in branch_groups.items():
        if len(group) > 1:
            print(f"Branch group for {reply_to}: {len(group)} messages")
            for i, msg in enumerate(sorted(group, key=lambda m: m.timestamp)):
                print(f"  [{i}] {msg.id}: {msg.text[:30]}...")
            print()
    
    # Simulate JavaScript path building logic
    print("=== Path Building Logic ===")
    
    # Find latest message
    latest_msg = max(messages, key=lambda m: m.timestamp)
    print(f"Latest message: {latest_msg.id} - {latest_msg.text[:30]}...")
    
    # Build message lookup
    msg_by_id = {m.id: m for m in messages}
    
    # Build path backwards (default - no branch selections)
    path_ids = set()
    current = latest_msg
    
    print("\nBuilding path backwards:")
    while current:
        print(f"  Adding to path: {current.id} - {current.text[:30]}...")
        path_ids.add(current.id)
        
        reply_to = current.reply_to_message_id
        if reply_to:
            # Check if there are branches
            branches = [m for m in messages if m.reply_to_message_id == reply_to]
            if len(branches) > 1:
                # Default to latest branch
                branches.sort(key=lambda m: m.timestamp)
                selected_branch = branches[-1]  # Latest
                print(f"    Found {len(branches)} branches, selecting latest: {selected_branch.id}")
                current = selected_branch
            else:
                current = branches[0] if branches else None
            
            # Move to parent
            if current:
                current = msg_by_id.get(reply_to)
        else:
            current = None
    
    print(f"\nDefault path contains {len(path_ids)} messages:")
    for msg in messages:
        if msg.id in path_ids:
            print(f"  ✓ {msg.id}: {msg.text[:50]}...")
        else:
            print(f"  ✗ {msg.id}: {msg.text[:50]}...")
    
    # Test branch selection change
    print("\n=== Testing Branch Selection Change ===")
    
    # Find a branch group to test with
    test_group = None
    test_reply_to = None
    for reply_to, group in branch_groups.items():
        if len(group) > 1:
            test_group = sorted(group, key=lambda m: m.timestamp)
            test_reply_to = reply_to
            break
    
    if test_group:
        print(f"Testing with branch group for {test_reply_to}:")
        for i, msg in enumerate(test_group):
            print(f"  [{i}] {msg.id}: {msg.text[:30]}...")
        
        # Test selecting first branch instead of latest
        branch_selections = {test_reply_to: 0}
        print(f"\nWith branch selection {test_reply_to}: 0")
        
        # This reveals the flaw: we need to rebuild the entire path
        # when branch selection changes, not just traverse from latest
        
        # The correct approach: find all possible paths and select based on branch choices
        print("Current logic is flawed - need to rebuild path from branch selections")

if __name__ == '__main__':
    debug_branching_logic()
