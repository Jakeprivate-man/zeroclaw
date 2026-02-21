# Agent 02 Investigation Report: Parent-Child Agent Delegation in ZeroClaw

**Investigation Date**: 2026-02-21  
**Status**: Complete  
**Thoroughness Level**: Very High  

---

## Executive Summary

ZeroClaw implements a **linear delegation chain** architecture rather than a full hierarchical tree structure. While parent agents can delegate to child agents recursively, the system:

1. **Lacks explicit tree structure tracking** - no hierarchical relationship data is persisted or tracked
2. **Uses depth limits instead of tree tracking** - prevents circular delegation and runaway recursion via immutable `depth` counter
3. **Implements isolated sub-agent execution** - child agents use `NoopObserver` (no event bubbling to parent)
4. **Does not expose delegation lineage in observability** - no parent-child relationship events exist
5. **Is invisible in UI/gateway observability** - nested agent research pipelines cannot be visualized as trees

**Critical Finding**: The `NoopObserver` in delegated sub-agents means child agent execution is completely invisible to parent observability systems. This explains why nested research pipelines do not appear in the UI.

---

## 1. DelegateTool Implementation Deep Dive

### Location
`/Users/jakeprivate/zeroclaw/src/tools/delegate.rs` (1095 lines)

### Core Architecture

#### 1.1 DelegateTool Struct
```rust
pub struct DelegateTool {
    agents: Arc<HashMap<String, DelegateAgentConfig>>,
    security: Arc<SecurityPolicy>,
    fallback_credential: Option<String>,
    provider_runtime_options: providers::ProviderRuntimeOptions,
    depth: u32,  // ← Key: Immutable depth counter (set at construction)
    parent_tools: Arc<Vec<Arc<dyn Tool>>>,  // ← Tools available to agentic sub-agents
    multimodal_config: crate::config::MultimodalConfig,
}
```

**Key Insight**: `depth` is the ONLY mechanism for tracking delegation hierarchy. It's immutable and incremented only when constructing sub-agent tools (see line 72-103).

#### 1.2 Depth Management

**Construction Methods**:
- `DelegateTool::new()` - Depth 0 (root agent)
- `DelegateTool::with_depth(depth)` - Sets explicit depth (for sub-agents)
- `DelegateTool::with_depth_and_options()` - Depth + provider options

**Depth Increment Pattern**:
```rust
// Lines 72-85: Creating sub-agent DelegateTool
pub fn with_depth(
    agents: HashMap<String, DelegateAgentConfig>,
    fallback_credential: Option<String>,
    security: Arc<SecurityPolicy>,
    depth: u32,
) -> Self {
    // depth is passed in, immutable once set
    Self { depth, ... }
}
```

**Depth Limit Enforcement** (lines 218-230):
```rust
if self.depth >= agent_config.max_depth {
    return Ok(ToolResult {
        success: false,
        output: String::new(),
        error: Some(format!(
            "Delegation depth limit reached ({depth}/{max}). \
             Cannot delegate further to prevent infinite loops.",
            depth = self.depth,
            max = agent_config.max_depth
        )),
    });
}
```

**Max Depth Config** (`src/config/schema.rs` lines 208-210):
```rust
/// Max recursion depth for nested delegation
#[serde(default = "default_max_depth")]
pub max_depth: u32,  // Default: 3

fn default_max_depth() -> u32 { 3 }
```

### 1.3 Delegation Flow

#### Non-Agentic Mode (Simple Provider Call)
1. **Parent agent calls delegate tool** → `DelegateTool::execute()` (line 162)
2. **Depth check** (line 219) → Reject if depth >= max_depth
3. **Provider creation** (line 251-267) → Create provider for sub-agent model
4. **Message assembly** (line 270-274) → Combine context + prompt
5. **Single provider call** (line 292-300) → Timeout-wrapped call to sub-agent LLM
6. **Result return** (line 316-338) → Return text response to parent

**Time Budget**: 120 seconds (line 15: `DELEGATE_TIMEOUT_SECS`)

#### Agentic Mode (Tool-Call Loop)
1. **Parent agent calls delegate tool** with `agentic=true`
2. **Depth check** (line 219) → Same as above
3. **Tool filtering** (lines 361-374) → Create allowlist of parent tools for sub-agent
4. **Sub-agent tool loop** (lines 396-412) → Call `run_tool_call_loop()` with filtered tools
5. **NoopObserver injection** (line 393) → Sub-agent observability is SILENT
6. **Result aggregation** (line 416-446) → Final response to parent

**Time Budget**: 300 seconds (line 17: `DELEGATE_AGENTIC_TIMEOUT_SECS`)

---

## 2. Delegation Tree Structure Analysis

### Critical Finding: No Tree Structure Exists

The delegation system is **NOT a tree**. It is a **linear depth counter**:

```
Parent Agent (depth=0)
    └── Delegate Tool executed
        └── Sub-Agent Child (depth=1)
            └── Delegate Tool executed
                └── Sub-Agent Grandchild (depth=2)
                    └── Delegate Tool executed
                        └── Rejected: depth=2 >= max_depth=3 check would pass, but typically max_depth=2 per agent
```

**Why No Tree Tracking?**
1. **No parent reference**: Sub-agents do not know their parent's name or identity
2. **No sibling tracking**: Multiple delegations to different agents are independent
3. **No lineage storage**: No persistent delegation history or genealogy
4. **No UI representation**: Observability system has no delegation tree events

### 2.1 Parent-Child Relationship Metadata

| Aspect | Status | Location |
|--------|--------|----------|
| **Parent agent name** | Not tracked | - |
| **Child agent name** | Passed as param | `delegate.rs` line 163-167 |
| **Delegation reason** | Not stored | - |
| **Execution timestamp** | Not stored | - |
| **Delegation result** | Returned inline | `delegate.rs` line 323-330 |
| **Lineage chain** | Not maintained | - |
| **Recursive depth** | Tracked immutably | `delegate.rs` line 31 |

### 2.2 Circular Delegation Prevention

**Method**: Depth limit only (no cycle detection)
- **Default max_depth**: 3
- **Per-agent override**: Via `DelegateAgentConfig.max_depth`
- **Enforcement**: At delegation time (line 219)
- **No graph analysis**: No pre-check for cycles, only depth limit

**Example Prevention**:
```
Agent A (depth=0) → delegate to B
Agent B (depth=1) → delegate to A (would be depth=2)
Agent A (depth=2) → delegate to B (would be depth=3)
Agent B (depth=3) → REJECTED: depth=3 >= max_depth=2
```

But this is NOT a true cycle detection—it's just a "go too deep and fail" approach.

---

## 3. Sub-Agent Communication Protocol

### 3.1 Data Flow: Parent → Child

**Communication Channel**: Synchronous function call + timeout wrapper

**Message Format**:
```json
{
    "agent": "sub_agent_name",
    "prompt": "The task to perform",
    "context": "Optional: prior findings, code snippets, etc."
}
```

**Parameter Validation** (lines 163-195):
- `agent` - Required, non-empty, trimmed
- `prompt` - Required, non-empty, trimmed
- `context` - Optional, defaults to empty string

**Message Assembly** (lines 270-274):
```rust
let full_prompt = if context.is_empty() {
    prompt.to_string()
} else {
    format!("[Context]\n{context}\n\n[Task]\n{prompt}")
};
```

### 3.2 Data Flow: Child → Parent

**Return Format**: `ToolResult` struct (from `src/tools/traits.rs` lines 4-10):
```rust
pub struct ToolResult {
    pub success: bool,
    pub output: String,
    pub error: Option<String>,
}
```

**Non-Agentic Mode Response** (lines 323-330):
```rust
Ok(ToolResult {
    success: true,
    output: format!(
        "[Agent '{agent_name}' ({provider}/{model})]\n{rendered}",
        provider = agent_config.provider,
        model = agent_config.model
    ),
    error: None,
})
```

**Agentic Mode Response** (lines 424-431):
```rust
Ok(ToolResult {
    success: true,
    output: format!(
        "[Agent '{agent_name}' ({provider}/{model}, agentic)]\n{rendered}",
        provider = agent_config.provider,
        model = agent_config.model
    ),
    error: None,
})
```

**Error Response** (lines 434-437 or 439-444):
```rust
Ok(ToolResult {
    success: false,
    output: String::new(),
    error: Some(format!("Agent '{agent_name}' failed: {e}")),
})
```

### 3.3 Observability Isolation

**Critical Issue**: Child agents use `NoopObserver` (lines 393, 479-493)

```rust
struct NoopObserver;

impl Observer for NoopObserver {
    fn record_event(&self, _event: &ObserverEvent) {}  // ← SILENT
    fn record_metric(&self, _metric: &ObserverMetric) {}  // ← SILENT
    fn name(&self) -> &str { "noop" }
    fn as_any(&self) -> &dyn std::any::Any { self }
}
```

**What This Means**:
- Sub-agent LLM calls → Not visible in parent observability
- Sub-agent tool calls → Not visible in parent observability
- Sub-agent errors → Not visible in parent observability
- **Only the final result** is returned as a ToolResult

**Why This Decision?**
- Avoids polluting parent's observability stream
- Keeps parent-child boundary clear
- Sub-agent execution is "black box" to parent observer

---

## 4. Resource Isolation Model

### 4.1 Token Budget Delegation

**Token Tracking**: Per-agent, not per-delegation

| Component | Tracking | Location |
|-----------|----------|----------|
| **Parent agent tokens** | Tracked by parent provider | `src/agent/agent.rs` |
| **Child agent tokens** | Tracked by child provider | Each child's provider |
| **Cross-agent budget** | Not enforced | - |
| **Token limit** | Per-message or per-session | Config-dependent |

**Implication**: No parent-to-child token budget transfer. Each agent independently consumes its own token quota.

### 4.2 Memory Separation

**Memory Systems**:
1. **Parent memory** → Shared with parent agent
2. **Child memory** → Shared with child agent (agentic mode only)

**Agentic Mode Sub-Agent Creation** (lines 387-391):
```rust
let mut history = Vec::new();
if let Some(system_prompt) = agent_config.system_prompt.as_ref() {
    history.push(ChatMessage::system(system_prompt.clone()));
}
history.push(ChatMessage::user(full_prompt.to_string()));
```

**Memory NOT Shared**: Child agents in agentic mode do NOT share the parent's memory store (no `Memory` trait passed to tool loop).

### 4.3 Tool Access Control (Agentic Mode Only)

**Tool Allowlist Filtering** (lines 361-374):
```rust
let allowed = agent_config
    .allowed_tools
    .iter()
    .map(|name| name.trim())
    .filter(|name| !name.is_empty())
    .collect::<std::collections::HashSet<_>>();

let sub_tools: Vec<Box<dyn Tool>> = self
    .parent_tools
    .iter()
    .filter(|tool| allowed.contains(tool.name()))
    .filter(|tool| tool.name() != "delegate")  // ← Delegate tool explicitly excluded
    .map(|tool| Box::new(ToolArcRef::new(tool.clone())) as Box<dyn Tool>)
    .collect();
```

**Delegation Prevention**: The `delegate` tool is EXPLICITLY filtered out (line 372), preventing:
- Sub-agents from delegating further
- Deep delegation chains beyond intentional design
- Escape from intended tool allowlist

### 4.4 Resource Limits

| Resource | Limit | Config Location |
|----------|-------|-----------------|
| **Max delegation depth** | 0-N (default 3) | `DelegateAgentConfig.max_depth` |
| **Max iterations (agentic)** | 0-N (default 10) | `DelegateAgentConfig.max_iterations` |
| **Provider timeout** | 120s | `delegate.rs` line 15 |
| **Agentic timeout** | 300s | `delegate.rs` line 17 |
| **Message size** | Implicit (provider limit) | Provider-specific |

---

## 5. Observability & Telemetry

### 5.1 ObserverEvent System

**Defined Events** (`src/observability/traits.rs`):

| Event Type | Delegation Support | Details |
|------------|-------------------|---------|
| `AgentStart` | No parent ref | Only records current agent start |
| `LlmRequest` | Parent only | Parent's delegate tool call recorded as parent LLM |
| `LlmResponse` | Parent only | Parent's delegate tool response recorded as parent |
| `AgentEnd` | No parent ref | Only records current agent end |
| `ToolCallStart` | Name only | Records "delegate" as tool, not target agent |
| `ToolCall` | Name only | Records tool="delegate", no child identity |
| `TurnComplete` | No tree info | No delegation context |
| `ChannelMessage` | N/A | Not delegation-related |
| `HeartbeatTick` | N/A | Not delegation-related |
| `Error` | Component string | No parent-child error linking |

**Missing Events**:
- ❌ `DelegationStart { parent: str, child: str, depth: u32 }`
- ❌ `DelegationEnd { parent: str, child: str, duration: Duration, success: bool }`
- ❌ `SubAgentStart { parent: str, child: str, agentic: bool }`
- ❌ `SubAgentEnd { parent: str, child: str }`

### 5.2 How Child Execution is Hidden

**For Non-Agentic Delegates** (Simple provider call):
```
Parent Agent
  → DelegateTool.execute()
    → Provider.chat() [Synchronous, no observer event]
    → Return ToolResult
  → Observer.record_event(ToolCall { "delegate", ... })
```

**For Agentic Delegates** (Tool-call loop):
```
Parent Agent
  → DelegateTool.execute_agentic()
    → run_tool_call_loop(provider, tools, noop_observer, ...)
      [Internal LLM calls and tool calls recorded to noop_observer]
    → Return ToolResult
  → Observer.record_event(ToolCall { "delegate", ... })
```

**Key Difference**: `run_tool_call_loop()` is called with `noop_observer` (line 401), not the parent's observer:
```rust
let noop_observer = NoopObserver;
let result = tokio::time::timeout(
    Duration::from_secs(DELEGATE_AGENTIC_TIMEOUT_SECS),
    run_tool_call_loop(
        provider,
        &mut history,
        &sub_tools,
        &noop_observer,  // ← Silent execution
        &agent_config.provider,
        &agent_config.model,
        temperature,
        true,
        None,
        "delegate",
        &self.multimodal_config,
        agent_config.max_iterations,
        None,
        None,
    ),
).await;
```

---

## 6. Configuration & Wiring

### 6.1 Delegate Agent Configuration

**Location**: `src/config/schema.rs` lines 192-220

```rust
pub struct DelegateAgentConfig {
    pub provider: String,           // LLM provider (e.g., "openrouter")
    pub model: String,              // Model name (e.g., "anthropic/claude-sonnet")
    pub system_prompt: Option<String>,  // Optional system prompt override
    pub api_key: Option<String>,    // Optional API key override
    pub temperature: Option<f64>,   // Optional temperature override
    pub max_depth: u32,             // Max recursion depth (default 3)
    pub agentic: bool,              // Enable tool-call loop for sub-agent
    pub allowed_tools: Vec<String>, // Allowlist for agentic mode
    pub max_iterations: usize,      // Max tool iterations in agentic mode
}
```

**Registry**: Top-level config (line 183):
```rust
pub agents: HashMap<String, DelegateAgentConfig>,
```

### 6.2 Tool Wiring

**Location**: `src/tools/mod.rs` lines 272-300

```rust
if !agents.is_empty() {
    let delegate_agents: HashMap<String, DelegateAgentConfig> = 
        agents.iter().map(|(name, cfg)| (name.clone(), cfg.clone())).collect();
    
    let delegate_fallback_credential = fallback_api_key.and_then(|value| {
        let trimmed_value = value.trim();
        (!trimmed_value.is_empty()).then(|| trimmed_value.to_owned())
    });
    
    let parent_tools = Arc::new(tool_arcs.clone());  // ← All current tools become parent_tools
    
    let delegate_tool = DelegateTool::new_with_options(
        delegate_agents,
        delegate_fallback_credential,
        security.clone(),
        crate::providers::ProviderRuntimeOptions { ... },
    )
    .with_parent_tools(parent_tools)
    .with_multimodal_config(root_config.multimodal.clone());
    
    tool_arcs.push(Arc::new(delegate_tool));
}
```

**Key Insight**: `parent_tools` are all tools currently in the registry (line 282). This creates a **fixed set** of tools available to all potential child agents.

---

## 7. Current Limitations & Gaps

### 7.1 No Persistent Delegation History

| Feature | Available | Why Missing |
|---------|-----------|-------------|
| **Tree persistence** | ❌ | No database storage for relationships |
| **Lineage queries** | ❌ | No API to ask "who delegated to me?" |
| **Execution timeline** | ❌ | Events not linked across delegation boundary |
| **Breadcrumb trail** | ❌ | Child doesn't know parent name |

### 7.2 UI Visualization Impossibilities

**Current Observability Stream**:
```
ObserverEvent::ToolCall { "delegate", duration, success }
```

**What's Missing to Draw Tree**:
- ❌ Child agent name
- ❌ Delegation depth
- ❌ Parent agent identity
- ❌ Agentic vs non-agentic mode
- ❌ Sub-agent tool calls (because NoopObserver)
- ❌ Child agent LLM calls

**Conclusion**: The observability system as-is **cannot reconstruct the delegation tree** because the child agent's identity and execution details are completely hidden.

### 7.3 Observability Leakage in Gateway

**Gateway Handler** (`src/gateway/mod.rs` line 285):
```rust
pub observer: Arc<dyn crate::observability::Observer>,
```

The gateway has access to the observability backend, but there are no events available to consume for delegation trees.

---

## 8. Diagrams

### 8.1 Delegation Flow (Non-Agentic)

```
┌─────────────────────────────────────────────────────────────────┐
│ Parent Agent (depth=0)                                           │
│                                                                   │
│  User Message: "Research this topic"                            │
│      ↓                                                            │
│  Tool Call: delegate(agent="researcher", prompt="...")          │
│      ↓                                                            │
│  DelegateTool::execute()                                         │
│  ├─ Check depth: 0 < max_depth(3) ✓                            │
│  ├─ Create provider for "researcher"                            │
│  ├─ Build message: [Context] + [Task]                          │
│  ├─ Timeout wrap: 120s                                          │
│  └─ Call provider.chat_with_system()                            │
│      ↓ (INVISIBLE TO PARENT OBSERVER)                           │
│      │                                                            │
│      ├─────────────────────────────────────────────────────────┤
│      │ Child LLM Call (synchronous, no event recording)         │
│      │  Response: "Here are findings..."                        │
│      └─────────────────────────────────────────────────────────┤
│      ↑                                                            │
│  Return: ToolResult { success: true, output: "..." }            │
│      ↓                                                            │
│  Observer.record_event(ToolCall {                               │
│    tool: "delegate",  ← NO CHILD IDENTITY                       │
│    duration: Xms,                                               │
│    success: true                                                │
│  })                                                              │
│                                                                   │
│  Parent continues with: "Based on delegate result: ..."        │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Delegation Flow (Agentic)

```
┌─────────────────────────────────────────────────────────────────┐
│ Parent Agent (depth=0)                                           │
│                                                                   │
│  User Message: "Research and summarize"                         │
│      ↓                                                            │
│  Tool Call: delegate(agent="researcher", prompt="...", agentic) │
│      ↓                                                            │
│  DelegateTool::execute_agentic()                                │
│  ├─ Check depth: 0 < max_depth(3) ✓                            │
│  ├─ Check agentic: allowed_tools non-empty ✓                   │
│  ├─ Filter tools: Remove "delegate", keep others               │
│  ├─ Initialize history: [system_prompt, user_prompt]           │
│  ├─ Create NoopObserver  ← EVENT SINK                          │
│  ├─ Timeout wrap: 300s                                          │
│  └─ Call run_tool_call_loop(provider, tools, noop_observer)   │
│      ↓ (INVISIBLE TO PARENT OBSERVER)                           │
│      │                                                            │
│      ├──────────────────────────────────────────────────────────┤
│      │ Sub-Agent Tool-Call Loop                                 │
│      │                                                            │
│      │ Iteration 1:                                             │
│      │  ├─ LlmRequest { ... } → NoopObserver.record_event()   │
│      │  ├─ Provider.chat() → [tool_calls]                      │
│      │  ├─ LlmResponse { ... } → NoopObserver.record_event()  │
│      │  ├─ Execute tools → NoopObserver.record_event()         │
│      │  └─ Add tool results to history                         │
│      │                                                            │
│      │ Iteration 2:                                             │
│      │  ├─ LlmRequest { ... } → NoopObserver.record_event()   │
│      │  ├─ Provider.chat() → [text response, no tools]         │
│      │  └─ Exit loop                                            │
│      │                                                            │
│      │ Return: Final text from LLM                             │
│      └──────────────────────────────────────────────────────────┤
│      ↑                                                            │
│  Return: ToolResult { success: true, output: "..." }            │
│      ↓                                                            │
│  Observer.record_event(ToolCall {                               │
│    tool: "delegate",  ← NO CHILD IDENTITY OR ITERATIONS        │
│    duration: Xms,                                               │
│    success: true                                                │
│  })                                                              │
│                                                                   │
│  Parent continues with: "Based on delegate result: ..."        │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 Maximum Delegation Hierarchy

```
Agent A (provider=gpt4o, depth=0)
  │
  └─→ delegate(agent="B", max_depth=3)
      │
      Agent B (provider=claude, depth=1, max_depth=3)
      │
      └─→ delegate(agent="C", max_depth=3)
          │
          Agent C (provider=ollama, depth=2, max_depth=3)
          │
          └─→ delegate(agent="D", max_depth=3)
              │
              Agent D (provider=gemini, depth=3, max_depth=3)
              │
              └─→ ✗ REJECTED: depth(3) >= max_depth(3)
```

### 8.4 Observability Event Stream (Current)

```
Timeline:
─────────────────────────────────────────────────────────────────

[Agent Start] { provider: "openrouter", model: "gpt4o" }
    ↓
[LLM Request] { messages_count: 2 }
    ↓
[LLM Response] { duration: 150ms, success: true }
    ↓
[Tool Call Start] { tool: "delegate" }
    ↓
[INTERNAL SUB-AGENT EXECUTION - INVISIBLE]
    │  [Sub-Agent LLM Request]      → NoopObserver (lost)
    │  [Sub-Agent LLM Response]     → NoopObserver (lost)
    │  [Sub-Agent Tool Call: file]  → NoopObserver (lost)
    │  [Sub-Agent Tool Result]      → NoopObserver (lost)
    ↓ (end of invisibility)
    ↓
[Tool Call] { tool: "delegate", duration: 2500ms, success: true }
    ↓
[LLM Request] { messages_count: 3 }  ← Parent's next turn with delegate result
    ↓
[LLM Response] { duration: 200ms, success: true }
    ↓
[Turn Complete]
    ↓
[Agent End] { duration: 3s, tokens_used: None, cost_usd: None }
```

### 8.5 What a UI Would Need (Missing)

To visualize delegation trees, the observability system would need:

```rust
// Currently does NOT exist:
pub enum ObserverEvent {
    // ... existing variants ...
    
    // ❌ MISSING: Delegation start/end
    DelegationStart {
        parent_agent: String,     // e.g., "root"
        child_agent: String,      // e.g., "researcher"
        depth: u32,               // e.g., 1
        agentic: bool,            // e.g., true
        prompt: String,           // Task description
    },
    DelegationEnd {
        parent_agent: String,
        child_agent: String,
        depth: u32,
        duration: Duration,
        success: bool,
        error: Option<String>,
    },
    
    // ❌ MISSING: Sub-agent internal events forwarded to parent
    SubAgentEvent {
        parent: String,
        child: String,
        depth: u32,
        event: Box<ObserverEvent>,  // Nested event (LLM call, tool call, etc.)
    },
}
```

---

## 9. Code References & Test Evidence

### 9.1 Depth Limit Tests

**File**: `src/tools/delegate.rs` lines 742-762

```rust
#[tokio::test]
async fn depth_limit_enforced() {
    let tool = DelegateTool::with_depth(sample_agents(), None, test_security(), 3);
    let result = tool
        .execute(json!({"agent": "researcher", "prompt": "test"}))
        .await
        .unwrap();
    assert!(!result.success);
    assert!(result.error.unwrap().contains("depth limit"));
}

#[tokio::test]
async fn depth_limit_per_agent() {
    // coder has max_depth=2, so depth=2 should be blocked
    let tool = DelegateTool::with_depth(sample_agents(), None, test_security(), 2);
    let result = tool
        .execute(json!({"agent": "coder", "prompt": "test"}))
        .await
        .unwrap();
    assert!(!result.success);
    assert!(result.error.unwrap().contains("depth limit"));
}
```

### 9.2 Agentic Mode Tests

**File**: `src/tools/delegate.rs` lines 1010-1053

```rust
#[tokio::test]
async fn execute_agentic_runs_tool_call_loop_with_filtered_tools() {
    // Proves agentic mode uses tool filtering
    let config = agentic_config(vec!["echo_tool".to_string()], 10);
    let tool = DelegateTool::new(HashMap::new(), None, test_security())
        .with_parent_tools(Arc::new(vec![
            Arc::new(EchoTool),
            Arc::new(DelegateTool::new(HashMap::new(), None, test_security())),
        ]));
    // ...
}

#[tokio::test]
async fn execute_agentic_excludes_delegate_even_if_allowlisted() {
    // Proves delegate tool is explicitly excluded
    let config = agentic_config(vec!["delegate".to_string()], 10);
    // ... should fail because delegate is filtered out
}
```

### 9.3 Configuration Examples

**File**: `src/config/schema.rs` lines 222-228

```rust
fn default_max_depth() -> u32 { 3 }
fn default_max_tool_iterations() -> usize { 10 }
```

---

## 10. UI Visualization Requirements (Critical Gap)

### 10.1 What Would Be Required

To surface nested agent research pipelines in the UI, the following changes would be needed:

#### Option A: Observability Events (Recommended)
1. **Add new ObserverEvent variants** for delegation start/end
2. **Propagate child events to parent observer** (not NoopObserver)
3. **Add parent/child context to all events** during delegation
4. **Modify run_tool_call_loop()** to accept observer parameter and context
5. **Update gateway observability handler** to record delegation tree events
6. **Implement tree reconstruction logic** in UI backend

#### Option B: Delegation History Store (Database)
1. **Create delegation event log** table
2. **Record at delegation start**: parent name, child name, depth, agentic mode
3. **Record at delegation end**: result, duration, success/failure
4. **Query API**: `GET /api/delegations` returns tree structure
5. **Update UI** to fetch and render delegation tree

#### Option C: Hybrid (Best)
- **Use Observability** for real-time events (streaming)
- **Use Delegation Store** for historical queries and tree reconstruction
- **UI renders** from both sources

### 10.2 Estimated Implementation Effort

| Component | Effort | Files | Complexity |
|-----------|--------|-------|------------|
| ObserverEvent variants | 1-2 hours | `src/observability/traits.rs` | Low |
| DelegateTool instrumentation | 2-3 hours | `src/tools/delegate.rs` | Low-Medium |
| run_tool_call_loop() forwarding | 2-3 hours | `src/agent/loop_.rs` | Medium |
| Gateway events handler | 1-2 hours | `src/gateway/mod.rs` | Medium |
| UI tree renderer | 4-8 hours | Frontend | Medium-High |
| **Total** | **10-18 hours** | Multiple | Moderate |

---

## 11. Security Analysis

### 11.1 Delegation Boundary Controls

| Control | Mechanism | Strength |
|---------|-----------|----------|
| **Recursion depth** | Immutable depth counter | Strong |
| **Circular delegation** | Depth limit prevents deep cycles | Moderate (not true cycle detection) |
| **Tool access** | Allowlist filtering | Strong (agentic mode only) |
| **Credential isolation** | Per-agent API key override | Strong |
| **Execution isolation** | NoopObserver + timeout | Strong (but invisible) |
| **Information leakage** | No tree persistence | Good (but hides execution) |

### 11.2 Risks

1. **Token exhaustion**: A malicious parent could delegate repeatedly to consume tokens
2. **Timeout abuse**: Agentic mode 300s timeout × multiple delegations = long total time
3. **Tool escape**: If allowlist not carefully managed, sub-agents could use unintended tools

---

## 12. Summary & Recommendations

### 12.1 Key Findings

1. **Delegation is linear, not hierarchical** - Only depth counter, no tree structure
2. **Child execution is invisible** - NoopObserver blocks all observability
3. **No persistent history** - Delegation lineage not stored
4. **UI cannot visualize trees** - Missing observability events and event forwarding
5. **Configuration is per-agent** - Each agent independently configured in TOML

### 12.2 Why Nested Research Pipelines Don't Appear in UI

```
Reason 1: NoopObserver in run_tool_call_loop()
  └─ Sub-agent LLM/tool calls not recorded
  
Reason 2: No DelegationStart/DelegationEnd events
  └─ No way to reconstruct tree from event stream
  
Reason 3: Child identity not in ToolCall event
  └─ Only "delegate" tool name, not target agent name
  
Reason 4: No delegation history database
  └─ No persistent lineage data after execution ends
  
Result: UI has ZERO information about delegated sub-agents
```

### 12.3 Actionable Recommendations

**Short Term (Quick Wins)**:
1. **Log child agent names** at delegation start/end (log only, not observability)
2. **Add debug tracing** to DelegateTool to track delegation chain
3. **Document current limitations** in delegation design docs

**Medium Term (Observability Upgrade)**:
1. **Add ObserverEvent::DelegationStart** and **DelegationEnd** variants
2. **Modify DelegateTool** to emit these events
3. **Update gateway** to record delegation events
4. **Create delegation timeline** view in UI (flat list before tree)

**Long Term (Full Tree UI)**:
1. **Implement delegation event forwarding** from child to parent observer
2. **Reconstruct delegation tree** in UI from event stream
3. **Render interactive tree visualization** with expand/collapse
4. **Add filtering** for depth, agent name, success/failure

### 12.4 Final Assessment

**Current State**: Delegation works functionally but is **invisible to monitoring/UI** due to architectural isolation.

**Design Philosophy**: The NoopObserver is intentional—it keeps delegation clean and isolated, but the tradeoff is zero observability.

**Path Forward**: Adding delegation observability events is straightforward and would immediately enable UI visualization without breaking existing functionality.

---

## Appendix: Configuration Example

```toml
# config.toml

[agents.researcher]
provider = "openrouter"
model = "anthropic/claude-sonnet-4-20250514"
system_prompt = "You are a research assistant."
temperature = 0.3
max_depth = 2
agentic = true
allowed_tools = ["shell", "file_read", "http_request", "web_search_tool"]
max_iterations = 15

[agents.summarizer]
provider = "ollama"
model = "neural-chat:latest"
system_prompt = "Summarize research findings concisely."
api_key = "ollama_key_override"
temperature = 0.5
max_depth = 1
agentic = false
```

When parent agent calls:
```python
delegate(agent="researcher", prompt="Research ZeroClaw delegation", agentic=true)
```

Execution:
1. Parent DelegateTool (depth=0) spawns researcher
2. Researcher gets depth=1, runs tool-call loop with allowed_tools
3. Researcher can call shell, file_read, http_request, web_search
4. Researcher cannot call delegate (filtered out)
5. All execution invisible to parent observer (NoopObserver)
6. Result returned as ToolResult to parent

---

**Report Generated**: 2026-02-21  
**Investigator**: Agent 02  
**Status**: Complete  
**Recommendation**: Proceed with observability enhancement design
