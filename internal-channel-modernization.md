# Internal Channel Modernization for Agent-to-Agent Communication

## Issue Summary

The Internal channel platform exists in Unicom but is currently in a legacy state. While functional, it needs modernization to support proper agent-to-agent communication in the new architecture, enabling better separation of concerns between AI agents.

## Current State Analysis

### ✅ What Works
- Internal platform is defined in `unicom.models.constants.channels`
- Complete service layer exists (`save_internal_message.py`, `send_internal_message.py`)
- Integration with reply system (`reply_to_message.py`)
- Used by LLM tool system for system accounts

### ❌ Legacy Issues
- References to non-existent fields: `message.target_function`, `message.triggered_function_calls`
- Old "Functions" and "entrypoints" architecture completely removed
- No modern Channel creation/validation for Internal platform
- Missing integration with current Request/LLM system

### 🔧 Current Usage
```python
# Only used internally by LLM tool system
account = Account.objects.create(
    platform='Internal',
    name=f'Tool: {tool_name}',
    # ...
)
```

## Required Modernization

### 1. Channel Integration
- Add Internal channel support to `Channel.validate()` method
- Create proper channel configuration handling
- Add admin interface support

### 2. Agent Communication Protocol
- Design agent-to-agent message routing
- Implement agent discovery/registration system  
- Add message queuing for async communication
- Support for broadcast and direct messaging

### 3. Request System Integration
- Connect Internal messages to Request processing
- Enable LLM context sharing between agents
- Support tool call delegation between agents

### 4. Clean Up Legacy Code
- Remove references to `target_function` and `triggered_function_calls`
- Update documentation to reflect current architecture
- Add proper error handling for missing fields

## Use Cases

### Modular Agent Architecture
```python
# Agent A requests data processing from Agent B
agent_a.send_to_agent('data_processor_agent', {
    'action': 'process_dataset',
    'data': dataset,
    'callback_channel': 'telegram_bot_123'
})

# Agent B processes and responds
agent_b.respond_to_agent('main_agent', {
    'result': processed_data,
    'status': 'completed'
})
```

### Separation of Concerns
- **Customer Service Agent**: Handles user interactions
- **Data Processing Agent**: Handles heavy computations  
- **Notification Agent**: Manages alerts and reminders
- **Analytics Agent**: Processes metrics and reporting

## Implementation Priority

1. **High**: Clean up legacy references and fix broken code paths
2. **Medium**: Add proper Channel validation and admin support
3. **Medium**: Implement basic agent-to-agent messaging
4. **Low**: Advanced features (queuing, discovery, broadcasting)

## Benefits

- **Modularity**: Separate agents for different responsibilities
- **Scalability**: Agents can run on different processes/servers
- **Maintainability**: Cleaner code separation
- **Flexibility**: Easy to add/remove specialized agents
- **Performance**: Distribute workload across agents

---

**Labels**: enhancement, architecture, internal-channel, agent-communication
**Priority**: Medium
**Effort**: Investigation needed
