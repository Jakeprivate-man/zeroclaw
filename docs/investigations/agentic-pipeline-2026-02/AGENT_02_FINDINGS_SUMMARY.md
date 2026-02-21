# Agent 02: Key Findings Summary

**Investigation Scope**: Parent-child agent delegation in ZeroClaw  
**Report Location**: `/Users/jakeprivate/zeroclaw/AGENT_02_DELEGATE_REPORT.md`  
**Status**: Complete (914-line comprehensive report)

---

## Critical Discovery

**The `NoopObserver` pattern is why nested agent research pipelines are invisible in the UI.**

When a parent agent delegates to a child agent (agentic mode), all child execution—LLM calls, tool calls, tool results, errors—is recorded to a `NoopObserver` that does NOTHING:

```rust
struct NoopObserver;
impl Observer for NoopObserver {
    fn record_event(&self, _event: &ObserverEvent) {}  // ← SILENT
    fn record_metric(&self, _metric: &ObserverMetric) {}  // ← SILENT
}
```

**Location**: `src/tools/delegate.rs` lines 393, 479-493

---

## System Architecture Summary

### Delegation Model: Linear, Not Hierarchical

ZeroClaw does NOT have a tree data structure for delegations. Instead:

1. **Depth Counter Only**: Each `DelegateTool` has an immutable `depth: u32` field
2. **Depth Limit Enforcement**: Blocks delegation if `depth >= agent_config.max_depth` (default 3)
3. **No Parent Reference**: Child agents don't know their parent's name
4. **No Sibling Tracking**: No awareness of other delegations at same level
5. **No Persistence**: Delegation lineage is never stored

### Observable Result

| Aspect | Status | Impact |
|--------|--------|--------|
| Parent→Child calls | Visible | Single `ToolCall { "delegate" }` event |
| Child LLM calls | Hidden | NoopObserver silences them |
| Child tool calls | Hidden | NoopObserver silences them |
| Child errors | Hidden | NoopObserver silences them |
| Delegation chain | Not tracked | No way to reconstruct hierarchy |

---

## Key Implementation Points

### 1. DelegateTool Core Fields
- **agents**: HashMap of named agent configs
- **depth**: Immutable depth counter (set at construction)
- **parent_tools**: Allowlist of tools for agentic sub-agents
- **Security**: Per-tool security policy enforcement

### 2. Delegation Modes

#### Non-Agentic (Simple)
- Single provider call (120s timeout)
- No tool loop
- Result returned directly to parent

#### Agentic (Full Loop)
- Multiple LLM+tool iterations (300s timeout)
- Tool allowlist filtering (delegate tool explicitly excluded)
- NoopObserver silences all internal events
- Result aggregated and returned to parent

### 3. Resource Limits
- **Max depth**: 3 (per-agent override possible)
- **Max iterations** (agentic): 10
- **Provider timeout**: 120s (non-agentic), 300s (agentic)
- **No token budget transfer**: Each agent tracks its own

### 4. Tool Access Control
```rust
// Agentic sub-agents get filtered tool set:
allowed_tools
  .filter(|tool| tool.name() != "delegate")  // Prevent further delegation
  .collect()
```

---

## Missing Observability Events

**To visualize delegation trees in UI, these events MUST be added:**

```rust
DelegationStart {
    parent_agent: String,    // ❌ Currently not emitted
    child_agent: String,     // ❌ Currently not emitted
    depth: u32,              // ❌ Currently not emitted
    agentic: bool,           // ❌ Currently not emitted
}

DelegationEnd {
    parent_agent: String,    // ❌ Currently not emitted
    child_agent: String,     // ❌ Currently not emitted
    depth: u32,              // ❌ Currently not emitted
    duration: Duration,      // ❌ Currently not emitted
    success: bool,           // ❌ Currently not emitted
    error: Option<String>,   // ❌ Currently not emitted
}

SubAgentEvent {
    parent: String,          // ❌ Currently not emitted
    child: String,           // ❌ Currently not emitted
    depth: u32,              // ❌ Currently not emitted
    event: Box<ObserverEvent>, // ❌ Child events not forwarded
}
```

---

## Why UI Cannot Show Delegation Trees

### Current Observability Stream
```
AgentStart { provider, model }
  → LlmRequest { messages: 2 }
  → LlmResponse { duration: 150ms }
  → ToolCall { tool: "delegate" }  ← Only this, NO CHILD IDENTITY
  → LlmRequest { messages: 3 }
  → LlmResponse { duration: 200ms }
  → AgentEnd { duration: 3s }
```

### What's Missing
- Child agent name
- Whether agentic or simple delegation
- Delegation depth
- Child's LLM calls
- Child's tool calls
- Child's errors
- Execution timeline within child

**Result**: UI has ZERO information to reconstruct the delegation tree.

---

## Code Evidence

### Depth Limit Enforcement
**File**: `src/tools/delegate.rs` lines 218-230
```rust
if self.depth >= agent_config.max_depth {
    return Ok(ToolResult {
        success: false,
        error: Some(format!(
            "Delegation depth limit reached ({depth}/{max}). \
             Cannot delegate further to prevent infinite loops."
        )),
    });
}
```

### NoopObserver Injection
**File**: `src/tools/delegate.rs` line 393
```rust
let noop_observer = NoopObserver;
let result = run_tool_call_loop(
    // ...
    &noop_observer,  // ← Silent execution
    // ...
)
```

### Tool Filtering (Explicit Delegate Exclusion)
**File**: `src/tools/delegate.rs` line 372
```rust
.filter(|tool| tool.name() != "delegate")  // Prevent further delegation
```

---

## Configuration Example

```toml
# config.toml

[agents.researcher]
provider = "openrouter"
model = "anthropic/claude-sonnet-4-20250514"
system_prompt = "You are a research assistant."
max_depth = 2
agentic = true
allowed_tools = ["shell", "file_read", "http_request"]
max_iterations = 15

[agents.summarizer]
provider = "ollama"
model = "neural-chat:latest"
max_depth = 1
agentic = false
```

---

## Recommendations (Priority Order)

### 1. Add Observability Events (4-6 hours)
- Add `DelegationStart` and `DelegationEnd` variants to `ObserverEvent`
- Emit these in `DelegateTool::execute()` and `execute_agentic()`
- Update gateway to record delegation events

**Impact**: UI can now track delegation start/end, depth, agent names

### 2. Forward Child Events (6-10 hours)
- Replace `NoopObserver` with parent observer in agentic mode
- Add parent/child context to all events
- Modify `run_tool_call_loop()` to accept observer + context

**Impact**: UI can see full child execution timeline

### 3. Implement UI Tree Renderer (8-12 hours)
- Build tree reconstruction logic from event stream
- Create interactive tree visualization component
- Add filtering/search by agent, depth, duration

**Impact**: Nested research pipelines visible as expandable tree in UI

---

## Security Implications

### Current Strengths
- Depth limit prevents infinite recursion
- Tool allowlist prevents unintended tool access
- NoopObserver prevents observability pollution
- Credentials isolated per agent

### Potential Risks
- Token exhaustion if parent delegates repeatedly
- Long timeout chains (300s × 3 levels = 15 minutes)
- Tool allowlist management complexity if not careful

---

## Testing Coverage

**Tests Confirming Findings**:
- `depth_limit_enforced()` - Proves depth enforcement
- `depth_limit_per_agent()` - Proves per-agent limits
- `execute_agentic_excludes_delegate()` - Proves delegate tool filtered
- `execute_agentic_runs_tool_call_loop()` - Proves tool filtering works

**File**: `src/tools/delegate.rs` lines 742-1093

---

## Next Steps for Visibility

1. **Read full report**: `/Users/jakeprivate/zeroclaw/AGENT_02_DELEGATE_REPORT.md`
2. **Implement Option A** (Observability Events) for quick UI improvement
3. **Consider Option C** (Hybrid) for complete solution
4. **Update docs** to explain delegation tree visibility limitations

---

**Investigation Completed**: 2026-02-21  
**Report Size**: 914 lines (comprehensive)  
**Confidence Level**: Very High (code evidence + test confirmation)
