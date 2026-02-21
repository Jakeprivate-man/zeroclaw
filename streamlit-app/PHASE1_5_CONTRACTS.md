# Phase 1.5: Core Messaging - Shared Contracts

**Date:** 2026-02-21
**Purpose:** Define shared interfaces between all 5 components

---

## Data Structures

### Message Format
```python
{
    "role": "user" | "assistant" | "system",
    "content": str,
    "timestamp": float,  # Unix timestamp
    "id": str,  # Unique message ID
    "metadata": {
        "model": str,
        "tokens": int,
        "cost": float
    }
}
```

### Conversation Format
```python
{
    "id": str,
    "title": str,
    "created": float,
    "modified": float,
    "messages": List[Message],
    "model": str,
    "tags": List[str]
}
```

---

## Session State Keys

### Core Chat State
- `chat_messages`: List[Message] - Current conversation messages
- `chat_model`: str - Selected model (default: "glm-5")
- `chat_temperature`: float - Model temperature (default: 0.7)
- `chat_input`: str - Current text input value

### Conversation Management
- `conversations`: List[Conversation] - All saved conversations
- `current_conversation_id`: Optional[str] - Active conversation ID
- `conversation_directory`: str - Storage path (default: "~/.zeroclaw/conversations/")

### Realtime State
- `chat_polling`: bool - Whether polling is active
- `chat_last_check`: float - Last poll timestamp
- `chat_poll_interval`: int - Seconds between polls (default: 2)

---

## Component APIs

### 1. Message History (`components/chat/message_history.py`)

**Function:** `render_message_history()`

**Reads:**
- `st.session_state.chat_messages`

**Writes:**
- None (display only)

**Styling:**
- User messages: Light green background (#5FAF87 @ 10%)
- Assistant messages: Sea green background (#87D7AF @ 10%)
- Scrollable container
- Timestamps in small font

---

### 2. Message Input (`components/chat/message_input.py`)

**Function:** `render_message_input() -> Optional[str]`

**Reads:**
- `st.session_state.chat_model`
- `st.session_state.chat_temperature`

**Writes:**
- `st.session_state.chat_messages` (appends new message)

**Returns:**
- Message text if sent, None otherwise

**Features:**
- Character counter
- Model selector dropdown
- Temperature slider
- Send button + Enter key support

---

### 3. Conversation Manager (`lib/conversation_manager.py`)

**Class:** `ConversationManager`

**Methods:**
```python
save_conversation(conversation: Conversation) -> str:
    """Save conversation to disk, return ID"""

load_conversation(conversation_id: str) -> Conversation:
    """Load conversation from disk"""

list_conversations() -> List[Conversation]:
    """List all saved conversations"""

delete_conversation(conversation_id: str) -> bool:
    """Delete conversation, return success"""

get_storage_path() -> str:
    """Get conversations directory path"""
```

**Storage Format:**
- Location: `~/.zeroclaw/conversations/`
- Filename: `{conversation_id}.json`
- Index file: `conversations_index.json` (metadata only)

---

### 4. Realtime Poller (`lib/realtime_poller.py`)

**Function:** `poll_for_updates() -> bool`

**Purpose:**
- Check for new messages from agent
- Trigger UI refresh with `st.rerun()`

**Reads:**
- `st.session_state.chat_polling`
- `st.session_state.chat_last_check`
- `st.session_state.chat_poll_interval`

**Writes:**
- `st.session_state.chat_messages` (if new messages found)
- `st.session_state.chat_last_check`

**Returns:**
- True if updates found, False otherwise

**Implementation:**
- Use `st.empty()` for live updates
- Check timestamp of last message
- Compare with agent's latest response
- No WebSocket needed (use st.rerun())

---

### 5. Chat Page (`pages/chat.py`)

**Function:** `render()`

**Layout:**
```
┌────────────────────────────────────────────┐
│ Chat Interface                              │
├────────────────────────────────────────────┤
│                                             │
│  ┌───────────────┐  ┌────────────────────┐ │
│  │               │  │                    │ │
│  │  Message      │  │  Message Input     │ │
│  │  History      │  │  - Text area       │ │
│  │               │  │  - Model selector  │ │
│  │  (scrollable) │  │  - Send button     │ │
│  │               │  │  - Character count │ │
│  │               │  │                    │ │
│  └───────────────┘  └────────────────────┘ │
│   (60% width)        (40% width)           │
│                                             │
└────────────────────────────────────────────┘
```

**Integration:**
```python
# Left column: Message history
render_message_history()

# Right column: Input + controls
message = render_message_input()

# Handle new message
if message:
    # 1. Add to session state
    # 2. Send to agent (async)
    # 3. Poll for response
    # 4. Rerun UI
```

---

## Color Scheme (Matrix Green)

```python
COLORS = {
    "background": "#000000",
    "foreground": "#87D7AF",
    "primary": "#5FAF87",
    "secondary": "#2d5f4f",
    "border": "#2d5f4f",
    "accent": "#87D7AF",
    "user_message_bg": "rgba(95, 175, 135, 0.1)",
    "assistant_message_bg": "rgba(135, 215, 175, 0.1)",
    "error": "#FF5555",
    "warning": "#F1FA8C"
}
```

---

## Error Handling

### All Components Must:
1. Handle missing session state gracefully
2. Show error messages in Matrix Green theme
3. Never crash on invalid data
4. Log errors to console (optional debug mode)

### Standard Error Display:
```python
st.error("Error message here")  # Red border (preserved)
```

---

## File Structure

```
streamlit-app/
├── components/
│   └── chat/
│       ├── __init__.py
│       ├── message_history.py
│       └── message_input.py
├── lib/
│   ├── conversation_manager.py
│   └── realtime_poller.py
├── pages/
│   └── chat.py
└── PHASE1_5_CONTRACTS.md (this file)
```

---

## Testing Strategy

### Unit Tests
- Test each component in isolation
- Mock session state
- Verify correct reads/writes

### Integration Tests
- Test message flow (input → history)
- Test save/load conversation
- Test polling mechanism

### Manual Tests
1. Send a message → appears in history
2. Switch models → new messages use new model
3. Save conversation → reload → verify persistence
4. Poll for updates → UI refreshes automatically

---

## Success Criteria

1. ✅ All 5 files created
2. ✅ Components use shared contracts
3. ✅ No hardcoded values (use session state)
4. ✅ Matrix Green theme throughout
5. ✅ Error handling in place
6. ✅ Integration tested manually
7. ✅ No disconnects between components

---

**Next Steps:**
1. Build components in order (1→2→3→4→5)
2. Test each component individually
3. Integrate in chat.py
4. Validate end-to-end flow
