# Phase 1.5: Core Messaging - Architecture Diagram

**Date:** 2026-02-21

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Streamlit App                            │
│                          (app.py)                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                    ┌───────┴────────┐
                    │  Page Router   │
                    └───────┬────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────┐  ┌──────────────┐
    │  Dashboard   │ │   Chat   │  │  Analytics   │
    │     Page     │ │   Page   │  │     Page     │
    └──────────────┘ └────┬─────┘  └──────────────┘
                          │
                          │ (Phase 1.5 Focus)
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Message    │  │   Message    │  │  Realtime    │
│   History    │  │    Input     │  │   Poller     │
│  Component   │  │  Component   │  │  Component   │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       │                 │                 │
       └────────┬────────┴────────┬────────┘
                │                 │
                ▼                 ▼
        ┌───────────────┐ ┌──────────────┐
        │   Session     │ │ Conversation │
        │    State      │ │   Manager    │
        │  (Streamlit)  │ │   (lib/)     │
        └───────────────┘ └──────┬───────┘
                                 │
                                 ▼
                        ┌────────────────┐
                        │  File System   │
                        │ (~/.zeroclaw/  │
                        │ conversations/)│
                        └────────────────┘
```

---

## Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                       Chat Page                              │
│                     (pages/chat.py)                          │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Main Layout                         │  │
│  │                                                        │  │
│  │  ┌──────────────────┐    ┌──────────────────┐        │  │
│  │  │                  │    │                  │        │  │
│  │  │  Message History │    │  Message Input   │        │  │
│  │  │                  │    │                  │        │  │
│  │  │  ┌────────────┐  │    │  ┌────────────┐ │        │  │
│  │  │  │ User Msg 1 │  │    │  │ Text Area  │ │        │  │
│  │  │  └────────────┘  │    │  └────────────┘ │        │  │
│  │  │  ┌────────────┐  │    │  ┌────────────┐ │        │  │
│  │  │  │ Agent Msg 1│  │    │  │Model Select│ │        │  │
│  │  │  └────────────┘  │    │  └────────────┘ │        │  │
│  │  │  ┌────────────┐  │    │  ┌────────────┐ │        │  │
│  │  │  │ User Msg 2 │  │    │  │Send Button │ │        │  │
│  │  │  └────────────┘  │    │  └────────────┘ │        │  │
│  │  │                  │    │                  │        │  │
│  │  └───────┬──────────┘    └────────┬─────────┘        │  │
│  │          │                        │                  │  │
│  └──────────┼────────────────────────┼──────────────────┘  │
│             │                        │                     │
│             │  Reads chat_messages   │  Writes new message │
│             │                        │                     │
│             └────────────┬───────────┘                     │
│                          │                                 │
└──────────────────────────┼─────────────────────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │ Session State  │
                  │                │
                  │ chat_messages  │
                  │ chat_model     │
                  │ chat_temperature│
                  │ chat_polling   │
                  └────────────────┘
```

---

## Data Flow Diagram

```
User Action: "Send Message"
│
├──> 1. User types in text area
│         (components/chat/message_input.py)
│
├──> 2. User clicks "Send" button
│         ↓
│    create_message() creates message object
│         ↓
│    Message added to st.session_state.chat_messages
│         ↓
│    Returns message text to chat.py
│
├──> 3. Chat page handles message
│         (pages/chat.py)
│         ↓
│    handle_message_sent() processes message
│         ↓
│    simulate_agent_response() (placeholder)
│         ↓
│    add_assistant_message() adds response
│         ↓
│    start_waiting_for_response() enables polling
│         ↓
│    st.rerun() refreshes UI
│
├──> 4. UI refreshes
│         ↓
│    render_message_history() displays all messages
│         (components/chat/message_history.py)
│         ↓
│    User sees conversation updated
│
└──> 5. Polling continues
          (lib/realtime_poller.py)
          ↓
     auto_poll_in_background() checks for updates
          ↓
     If updates found → st.rerun()
```

---

## Conversation Persistence Flow

```
User Action: "Save Conversation"
│
├──> 1. User clicks "Save Conversation" in sidebar
│         (pages/chat.py)
│         ↓
│    Prompt for conversation title
│         ↓
│    User enters title
│
├──> 2. save_current_conversation() called
│         ↓
│    Gets messages from st.session_state.chat_messages
│         ↓
│    Gets model from st.session_state.chat_model
│         ↓
│    Calls ConversationManager.save_conversation()
│
├──> 3. ConversationManager saves to disk
│         (lib/conversation_manager.py)
│         ↓
│    Generate conversation ID (UUID)
│         ↓
│    Create conversation object:
│         {
│           id, title, created, modified,
│           messages, model, tags
│         }
│         ↓
│    Write to ~/.zeroclaw/conversations/{id}.json
│         ↓
│    Update conversations_index.json
│         ↓
│    Return conversation ID
│
└──> 4. Confirmation shown to user
          "Conversation saved! ID: {id[:8]}..."
```

```
User Action: "Load Conversation"
│
├──> 1. User selects conversation from dropdown
│         (pages/chat.py)
│         ↓
│    User clicks "Load" button
│
├──> 2. load_conversation() called
│         ↓
│    Calls ConversationManager.load_conversation(id)
│
├──> 3. ConversationManager loads from disk
│         (lib/conversation_manager.py)
│         ↓
│    Read ~/.zeroclaw/conversations/{id}.json
│         ↓
│    Parse JSON to conversation object
│         ↓
│    Return conversation dict
│
├──> 4. Conversation loaded into session state
│         ↓
│    st.session_state.chat_messages = conversation['messages']
│         ↓
│    st.session_state.chat_model = conversation['model']
│         ↓
│    st.session_state.current_conversation_id = id
│
└──> 5. UI refreshes with loaded conversation
          st.rerun()
```

---

## Session State Schema

```
st.session_state
│
├── chat_messages: List[Dict]
│   └── [
│         {
│           "id": "uuid-1",
│           "role": "user",
│           "content": "Hello",
│           "timestamp": 1234567890.0,
│           "metadata": {
│             "model": "glm-5",
│             "temperature": 0.7
│           }
│         },
│         {
│           "id": "uuid-2",
│           "role": "assistant",
│           "content": "Hi!",
│           "timestamp": 1234567891.0,
│           "metadata": {
│             "model": "glm-5",
│             "tokens": 50,
│             "cost": 0.001
│           }
│         }
│       ]
│
├── chat_model: str
│   └── "glm-5"
│
├── chat_temperature: float
│   └── 0.7
│
├── chat_polling: bool
│   └── False
│
├── chat_last_check: float
│   └── 1234567890.0
│
├── chat_poll_interval: int
│   └── 2
│
├── chat_waiting_for_response: bool
│   └── False
│
├── current_conversation_id: Optional[str]
│   └── "uuid-123"
│
├── conversation_title_prompt: bool
│   └── False
│
└── conversation_title: Optional[str]
    └── "My Conversation"
```

---

## File System Structure

```
~/.zeroclaw/
│
└── conversations/
    │
    ├── conversations_index.json
    │   └── {
    │         "conv-uuid-1": {
    │           "id": "conv-uuid-1",
    │           "title": "Debug Session",
    │           "created": 1234567890.0,
    │           "modified": 1234567891.0,
    │           "message_count": 10,
    │           "model": "glm-5",
    │           "tags": ["debug", "testing"]
    │         },
    │         "conv-uuid-2": { ... }
    │       }
    │
    ├── conv-uuid-1.json
    │   └── {
    │         "id": "conv-uuid-1",
    │         "title": "Debug Session",
    │         "created": 1234567890.0,
    │         "modified": 1234567891.0,
    │         "messages": [ ... ],
    │         "model": "glm-5",
    │         "tags": ["debug", "testing"]
    │       }
    │
    └── conv-uuid-2.json
        └── { ... }
```

---

## Component API Contracts

### Message History
```python
# Input (reads from session state)
st.session_state.chat_messages: List[Dict]

# Output (display only)
None

# Side Effects
- Renders HTML message cards
- No state mutations
```

### Message Input
```python
# Input (reads from session state)
st.session_state.chat_model: str
st.session_state.chat_temperature: float

# Output (writes to session state)
st.session_state.chat_messages.append(new_message)

# Returns
message_text: Optional[str]  # If sent, None otherwise

# Side Effects
- Creates message object
- Adds to messages list
- Clears input field
```

### Conversation Manager
```python
# Methods
save_conversation(messages, title, ...) -> str
load_conversation(conversation_id) -> Dict
list_conversations(...) -> List[Dict]
delete_conversation(conversation_id) -> bool
search_conversations(query) -> List[Dict]
export_conversation(id, format) -> str
get_stats() -> Dict

# Side Effects
- Reads/writes JSON files
- Updates index file
- No session state mutations
```

### Realtime Poller
```python
# Input (reads from session state)
st.session_state.chat_polling: bool
st.session_state.chat_last_check: float
st.session_state.chat_poll_interval: int

# Output (writes to session state)
st.session_state.chat_messages (if updates found)
st.session_state.chat_last_check

# Returns
bool  # True if updates found

# Side Effects
- May call st.rerun()
- Updates timestamps
```

---

## Error Handling Strategy

```
┌─────────────────────────────────────────┐
│           User Action                    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
          ┌───────────────┐
          │  Try Block    │
          │               │
          │  Component    │
          │  Logic        │
          └───┬───────┬───┘
              │       │
      Success │       │ Exception
              │       │
              ▼       ▼
      ┌──────────┐ ┌──────────────┐
      │ Continue │ │ Catch Block  │
      │ Normal   │ │              │
      │ Flow     │ │ st.error()   │
      └──────────┘ │ Log to       │
                   │ console      │
                   │ (if debug)   │
                   │              │
                   │ Graceful     │
                   │ fallback     │
                   └──────────────┘
```

### Example Error Handlers

1. **File operations** (ConversationManager)
   - Try: Read/write JSON file
   - Catch: Show error message, log exception
   - Fallback: Return None or empty list

2. **Session state access**
   - Use `.get()` with defaults
   - Never assume key exists
   - Initialize on first access

3. **User input validation**
   - Check character limits
   - Disable button if invalid
   - Show color-coded warnings

---

## Matrix Green Theme Application

```
┌─────────────────────────────────────────┐
│          Component Styling              │
├─────────────────────────────────────────┤
│                                         │
│  User Message Card:                     │
│  ┌───────────────────────────────────┐ │
│  │ bg: rgba(95, 175, 135, 0.1)      │ │
│  │ border: 1px solid #2d5f4f        │ │
│  │ color: #87D7AF                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Agent Message Card:                    │
│  ┌───────────────────────────────────┐ │
│  │ bg: rgba(135, 215, 175, 0.1)     │ │
│  │ border: 1px solid #2d5f4f        │ │
│  │ color: #87D7AF                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Buttons:                               │
│  ┌───────────────────────────────────┐ │
│  │ border: 1px solid #5FAF87        │ │
│  │ color: #5FAF87                   │ │
│  │ bg: transparent                  │ │
│  │ hover: bg #5FAF87, color #000    │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Character Counter:                     │
│  ┌───────────────────────────────────┐ │
│  │ < 80%: #87D7AF (green)           │ │
│  │ 80-100%: #F1FA8C (yellow)        │ │
│  │ > 100%: #FF5555 (red)            │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

---

## Integration Points for Phase 2

```
┌─────────────────────────────────────────┐
│         Current Implementation           │
│            (Phase 1.5)                   │
└───────────────┬─────────────────────────┘
                │
                │ Ready for:
                │
    ┌───────────┼───────────┐
    │           │           │
    ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│  Tool   │ │ Memory  │ │  Agent  │
│Approval │ │ Browser │ │   API   │
│(Phase 2)│ │(Phase 2)│ │Integration│
└─────────┘ └─────────┘ └─────────┘

Tool Approval:
- Intercept tool calls in message flow
- Show approval UI before execution
- Add approved/rejected metadata

Memory Browser:
- Read from ~/.zeroclaw/memory_store.json
- Display in sidebar or separate page
- Add/edit/delete via UI

Agent API Integration:
- Replace simulate_agent_response()
- Connect to ZeroClaw agent endpoint
- Real-time polling for responses
```

---

## Performance Considerations

### Polling Overhead
```
Polling Interval: 2 seconds (default)
├─> UI Rerun: ~100ms overhead
├─> State Check: < 1ms
└─> Network (future): TBD

Recommendation:
- Use 2-5 second intervals for balance
- Disable polling when not waiting
- Only rerun if updates found
```

### Session State Size
```
Average Message: ~500 bytes
100 Messages: ~50 KB
1000 Messages: ~500 KB

Recommendation:
- Limit in-memory messages to ~100
- Paginate history display if needed
- Archive old conversations to disk
```

### File I/O
```
Save Conversation: ~10-50ms
Load Conversation: ~5-20ms
List Conversations: ~1-5ms (index only)

Recommendation:
- Use index for listing (fast)
- Lazy-load full conversations
- Cache recently accessed
```

---

**Architecture Validated:** 2026-02-21
**Component Count:** 5 (message_history, message_input, conversation_manager, realtime_poller, chat page)
**Integration Status:** ✅ Cohesive and tested
