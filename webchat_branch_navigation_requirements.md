# WebChat Branch Navigation UI Requirements

## Current Backend Implementation
- User messages with same `reply_to_message_id` create branches
- Backend API returns all messages chronologically
- Context chain works via `reply_to_message` traversal

## Required UI Behavior

### Message Rendering Logic
1. **Scan messages for branching**: Find user messages with identical `reply_to_message_id` values
2. **Default selection**: Show chronologically latest message in each branch group
3. **Branch indicator**: Display `< 2 / 3 >` format showing current/total versions
4. **Navigation buttons**: `<` and `>` buttons to switch between versions
5. **Assistant response filtering**: Show only assistant messages that reply to currently selected user message

### Branch Selection Algorithm
1. **Recursive traversal**: Start from latest message, work backwards
2. **When branching found**: Skip all messages after the `reply_to_message` except those following selected branch
3. **Common messages**: Always show messages before branch points
4. **Performance**: O(N) complexity maximum

### Visual Requirements
- Branch navigation appears inline in message footer
- Format: `< current / total >` with disabled states for boundaries
- No complex navigation panels or separate UI elements
- Edit button remains functional alongside branch navigation

### Expected User Flow
1. **Default view**: Latest version of each branched message shown
2. **Click `<`**: Switch to previous chronological version
3. **Click `>`**: Switch to next chronological version  
4. **Assistant responses**: Update to match selected user message version
5. **Context preservation**: Messages before branch point remain visible

## Technical Notes
- Messages loaded via existing `branch=latest` API parameter
- Client-side processing required for branch detection and filtering
- State management needed for current selections per branch group
- Real-time updates must respect current branch selections
