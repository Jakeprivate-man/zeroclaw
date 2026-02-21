# ZeroClaw Interactivity - Quick Reference Guide

**Date:** 2026-02-21

---

## Interactive Controls Inventory (At-a-Glance)

### Agent Lifecycle (0% Complete)
- [ ] Start/Stop agent
- [ ] Pause/Resume agent  
- [ ] Restart failed agent
- [ ] View agent status
- [ ] List available agents

**Current:** No agent lifecycle API  
**Priority:** HIGH - Core functionality

---

### Message Operations (30% Complete)
- [x] Send message to agent
- [x] View message history (in-memory)
- [ ] Save conversation to disk
- [ ] Load previous conversation
- [ ] Search conversation history
- [ ] Clear conversation
- [ ] Export conversation

**Current:** Interactive CLI works, Streamlit UI needs implementation  
**Priority:** HIGH - Core functionality

---

### Tool Execution (0% Complete)
- [ ] Approve/reject pending tool calls
- [ ] View tool execution history
- [ ] Edit tool parameters before execution
- [ ] Dry-run tool execution
- [ ] Tool-specific permissions

**Current:** Agent auto-executes all tools (no approval)  
**Priority:** CRITICAL - Security issue

---

### Model Switching (0% Complete)
- [ ] Select model from list
- [ ] Switch model mid-session
- [ ] View model capabilities
- [ ] Compare model costs
- [ ] Adjust temperature/parameters

**Current:** Model fixed at agent creation  
**Priority:** HIGH - Common need

---

### Memory Management (10% Complete)
- [x] Store key-value pairs (tool exists)
- [x] Search memory (tool exists)
- [ ] View all memory items
- [ ] Add/edit/delete via UI
- [ ] Export/import memory
- [ ] Organize by category
- [ ] Set TTL/expiration

**Current:** Memory tools work, but no UI  
**Priority:** MEDIUM - Storage utility

---

### Conversation Control (20% Complete)
- [x] Maintain conversation history (in-memory)
- [ ] Persist conversation to disk
- [ ] Save conversation with name
- [ ] Load and resume conversation
- [ ] Branch from conversation point
- [ ] Archive old conversations

**Current:** In-memory only, lost on restart  
**Priority:** HIGH - Important for UX

---

### Configuration (0% Complete)
- [ ] Change API endpoint without restart
- [ ] Change API key without restart
- [ ] Edit system prompt
- [ ] Toggle tools on/off
- [ ] Adjust parameters
- [ ] Save configuration profile
- [ ] Reset to defaults

**Current:** All config via CLI or env vars  
**Priority:** MEDIUM - Convenience feature

---

### Gateway Control (20% Complete)
- [x] Check health status (/health endpoint)
- [x] Get metrics (/metrics endpoint)
- [ ] Test webhooks
- [ ] Manage device pairing
- [ ] Adjust rate limits
- [ ] View request history

**Current:** Basic endpoints only  
**Priority:** MEDIUM - Operations/debugging

---

### Debug & Inspection (0% Complete)
- [ ] Enable debug mode
- [ ] View execution trace
- [ ] Inspect agent state
- [ ] View token usage per request
- [ ] Measure execution latency
- [ ] View error stack traces

**Current:** No debug capabilities  
**Priority:** MEDIUM - Developer feature

---

### Batch Operations (0% Complete)
- [ ] Upload batch file (CSV/JSON)
- [ ] Preview batch before execution
- [ ] Execute batch with progress
- [ ] Cancel running batch
- [ ] Export batch results
- [ ] Schedule batch for later

**Current:** No batch support  
**Priority:** LOW - Advanced feature

---

## What's Already Built (In Streamlit UI)

### Existing Components
```
streamlit-app/
├── lib/
│   ├── api_client.py          ✓ Gateway API client
│   ├── session_state.py       ✓ Session management
│   ├── budget_manager.py      ✓ Cost tracking
│   ├── costs_parser.py        ✓ Parse cost files
│   ├── agent_monitor.py       ✓ Agent status
│   └── mock_data.py           ✓ Test data
├── components/
│   ├── sidebar.py             ✓ Navigation
│   └── dashboard/
│       ├── cost_tracking.py   ✓ Cost display
│       ├── token_usage.py     ✓ Token stats
│       ├── real_time_metrics.py ✓ Metrics view
│       ├── agent_status_monitor.py ✓ Agent status
│       ├── quick_actions_panel.py ✓ Action buttons
│       └── activity_stream.py ✓ Activity log
├── pages/
│   ├── dashboard.py           ✓ Main dashboard
│   ├── analytics.py           ~ Stub
│   ├── reports.py             ~ Stub
│   ├── analyze.py             ~ Stub
│   └── settings.py            ~ Stub
└── app.py                     ✓ Main app entry
```

### Quick Actions Already Implemented
```python
# In quick_actions_panel.py:
- Restart Gateway
- Clear Cache
- Refresh Stats
- View Logs
- Start All Agents
- Pause All Agents
- Restart Failed Agents
- Clear Queue
- Backup Data
- Sync Remote
- Compact DB
- Export Logs
- System Report
- Analytics
- Diagnostics
- Email Summary
```

---

## What Needs To Be Built

### Phase 1: Core Messaging (Week 1-2)

**Goal:** Make basic message input and conversation work

Files to create/modify:
1. `components/message_input.py` - Text input component
2. `components/conversation_view.py` - Message history display
3. `lib/agent_interface.py` - Direct agent invocation
4. `pages/dashboard.py` - Integrate message components

Core functionality:
```python
# Send a message
message = st.text_area("Your message:")
if st.button("Send"):
    response = agent.ainvoke({"messages": [HumanMessage(message)]})
    st.write(response)

# View history
st.subheader("Conversation")
for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        st.write(f"You: {msg.content}")
    else:
        st.write(f"Agent: {msg.content}")
```

---

### Phase 2: Tool Approval & Memory (Week 2-3)

**Goal:** Add tool approval workflow and memory browser

Files to create:
1. `components/tool_approval.py` - Approval interface
2. `components/memory_browser.py` - Memory view/edit
3. `lib/tool_interceptor.py` - Intercept tool calls
4. `pages/memory.py` - Memory page

Tool approval flow:
```python
# Before tool execution:
1. Detect pending tool calls in LangGraph
2. Show approval UI
3. User approves/rejects
4. Execute if approved
5. Log action for audit
```

Memory browser:
```python
# Display all memory items:
memory = memory_recall("*")  # Get all
for key, value in memory.items():
    col1, col2, col3 = st.columns(3)
    col1.write(key)
    col2.write(value)
    col3.button("Delete")
```

---

### Phase 3: Conversation Persistence (Week 3-4)

**Goal:** Save/load conversations to disk

Files to create:
1. `lib/conversation_store.py` - File persistence
2. `components/conversation_manager.py` - Save/load UI
3. `pages/conversations.py` - Conversation browser

Storage format:
```json
{
  "id": "conv-uuid",
  "title": "Debug Session",
  "created": "2026-02-21T10:00:00Z",
  "modified": "2026-02-21T10:30:00Z",
  "tags": ["debug", "testing"],
  "messages": [
    {"type": "human", "content": "..."},
    {"type": "ai", "content": "..."}
  ]
}
```

---

### Phase 4: Model Switching (Week 4-5)

**Goal:** Allow users to change models without restart

Files to create:
1. `components/model_selector.py` - Model dropdown
2. `lib/model_config.py` - Model registry
3. Update `lib/agent_interface.py` - Support model switching

Implementation:
```python
# In app.py session state:
st.session_state.model = "glm-5"
st.session_state.temperature = 0.7

# In sidebar:
new_model = st.selectbox("Model:", ["gpt-4", "glm-5", "claude-3"])
if new_model != st.session_state.model:
    st.session_state.model = new_model
    st.session_state.agent = None  # Recreate agent
    st.rerun()
```

---

### Phase 5: Advanced Features (Week 5+)

**Goal:** Debug, batch operations, advanced memory

Files:
1. `pages/debug.py` - Debug mode
2. `pages/batch.py` - Batch operations
3. `components/execution_trace.py` - Trace viewer
4. `lib/batch_processor.py` - Batch execution

---

## Gateway Endpoints Needed

### Already Implemented
```
GET  /health                           (Working)
GET  /metrics                          (Working)
```

### For Phase 1-2 (Must Have)
```
POST /api/message                      (Send message to agent)
GET  /api/memory                       (List all memory)
POST /api/memory/search                (Search memory)
POST /api/memory/{key}                 (Store memory)
DELETE /api/memory/{key}               (Delete memory)
```

### For Phase 3-4 (Should Have)
```
POST /api/conversations                (Save conversation)
GET  /api/conversations                (List conversations)
GET  /api/conversations/{id}           (Get one conversation)
POST /api/config/model                 (Change model)
GET  /api/models                       (List models)
```

### For Phase 5 (Nice to Have)
```
POST /api/batch                        (Submit batch job)
GET  /api/batch/{id}                   (Get batch status)
GET  /api/tool-calls/pending           (Get pending approvals)
POST /api/tool-calls/{id}/approve      (Approve tool)
```

---

## Current Implementation Status

### What Works Now
- ✓ Gateway health check
- ✓ Cost tracking display
- ✓ Token usage display
- ✓ Agent status monitor stub
- ✓ Quick actions panel (simulated)
- ✓ Activity stream
- ✓ Settings page stub

### What's In Progress
- ~ Dashboard layout
- ~ Analytics page
- ~ Reports page
- ~ Analyze page
- ~ Settings configuration

### What's Not Started
- [ ] Message input/send
- [ ] Conversation view
- [ ] Conversation save/load
- [ ] Memory browser
- [ ] Tool approval
- [ ] Model selector
- [ ] Debug panel
- [ ] Batch operations
- [ ] Advanced memory management

---

## Testing Checklist

### Unit Tests to Add
```python
# lib/
- test_agent_interface.py
- test_conversation_store.py
- test_model_config.py
- test_memory_browser.py

# components/
- test_message_input.py
- test_conversation_view.py
- test_tool_approval.py
- test_model_selector.py
```

### Integration Tests
```python
# End-to-end flows:
- Send message -> Agent responds -> Add to history
- Save conversation -> Load conversation -> Verify contents
- Switch model -> New agent created -> Use new model
- Approve tool -> Tool executes -> Show result
- Search memory -> Get matching items
```

### Manual Testing
1. Send message and verify response appears
2. Clear and reload conversation
3. Switch models and verify model changes
4. Approve/reject tool and verify behavior
5. Search memory and verify results

---

## Security Checklist

### Before Production
- [ ] Never log API keys (use masked display)
- [ ] Validate all user input
- [ ] Use secrets management for API keys
- [ ] Implement role-based access control
- [ ] Audit log all user actions
- [ ] Rate limit API endpoints
- [ ] Sanitize all file paths
- [ ] Approve tool execution for shell commands
- [ ] Use HTTPS in production
- [ ] Implement CORS properly

---

## Deployment Checklist

### Prerequisites
- [ ] Python 3.8+
- [ ] Streamlit 1.20+
- [ ] zeroclaw_tools library installed
- [ ] API keys configured
- [ ] Gateway service running

### Installation
```bash
pip install streamlit zeroclaw-tools requests

cd streamlit-app
streamlit run app.py --server.port 8501
```

### Configuration
```bash
# .env or environment variables:
GATEWAY_URL=http://localhost:3000
API_KEY=your-api-key
DISCORD_TOKEN=xxx (if using Discord)
BRAVE_API_KEY=xxx (if using web search)
```

---

## Key Dependencies

### Python Packages
- streamlit >= 1.20
- requests >= 2.28
- langchain-core >= 0.1
- langchain-openai >= 0.1

### External Services
- ZeroClaw Gateway API (running locally or remote)
- LLM Provider (OpenAI, Anthropic, GLM, etc.)
- Optional: Brave Search API
- Optional: Discord Bot Token

---

## Architecture Decisions

### Message History Storage
**Decision:** Use Streamlit session_state for current session, persist to `~/.zeroclaw/conversations/` for long-term storage  
**Rationale:** Fast for active session, survives app restart, easy to manage

### Tool Approval Flow
**Decision:** Intercept tool calls in UI layer, show approval dialog  
**Rationale:** User-friendly, secure for dangerous operations (shell), doesn't require changing agent code

### Model Switching
**Decision:** Store model selection in session state, recreate agent when model changes  
**Rationale:** Simple to implement, preserves conversation history separately

### Memory Storage
**Decision:** Use existing `~/.zeroclaw/memory_store.json` with JSON format  
**Rationale:** Already implemented, easy to display and edit in UI

### Configuration
**Decision:** Store in session state with optional save to `~/.zeroclaw/config.json`  
**Rationale:** Hot-reload in UI, persistent across restarts if saved

---

## Next Steps

1. **Week 1:** Implement message input/output components
2. **Week 2:** Add conversation persistence
3. **Week 3:** Build tool approval workflow
4. **Week 4:** Add model selector
5. **Week 5:** Advanced features (batch, debug, etc.)

Each phase builds on previous, allowing incremental validation and deployment.

