# AGENTIC PIPELINE MASTER REPORT: Complete Architecture & Implementation Roadmap

**Date Generated**: 2026-02-21  
**Investigator**: Agent 12 (Master Synthesis)  
**Scope**: Complete ZeroClaw nested agent research pipeline  
**Status**: SYNTHESIS COMPLETE - READY FOR IMPLEMENTATION

---

## EXECUTIVE SUMMARY

### The Problem
The user **cannot visualize nested agent research pipelines** in the Streamlit UI. Parent agents can delegate to child agents recursively, but this delegation tree is **completely invisible** to monitoring systems, logging, and the UI dashboard.

### Root Cause Analysis

1. **Child agents execute with `NoopObserver`**: No observability events recorded
2. **No delegation tree tracking**: Linear depth counter only; no parent-child relationships
3. **Tool history never persisted**: Observer events are ephemeral; no JSONL file written
4. **Real-time data gaps**: UI polls mock data instead of actual execution events
5. **Audit trail missing**: Delegation chain and approval history not captured

### Impact

- **Zero visibility** into nested agent research progress
- **No audit trail** of delegation chains
- **Missing tool history** for compliance/debugging
- **Brittle dashboard** depending on mock data instead of real execution

### Path Forward

Three-phase implementation to make nested research pipelines visible:

- **Phase 1 (Quick Wins)**: Basic delegation visibility + tool history (1-2 weeks)
- **Phase 2 (Data Infrastructure)**: Complete observability + session tracking (2-3 weeks)
- **Phase 3 (Advanced UI)**: Interactive visualization + real-time monitoring (3-4 weeks)

---

## 1. CRITICAL FINDINGS SYNTHESIS

### From Agent 1 (Lifecycle)
The agent lifecycle is well-architected with explicit state transitions. However:
- No formal state enum; state is implicit in execution flow
- No state snapshot API for UI to query current phase
- Tool execution results stored only in ephemeral conversation history

### From Agent 2 (Delegation) - CRITICAL
**This is the root cause of the nested pipeline invisibility:**

- Delegation uses linear depth counter (0, 1, 2...) instead of tree structure
- Child agents execute with `NoopObserver` - all internal events are **LOST**
- No `DelegationStart` or `DelegationEnd` events exist
- Child agent name not captured in parent's ToolCall event
- Result: **Complete architectural isolation** between parent and child

**Quoted from Agent 2 Report:**
> "The NoopObserver in delegated sub-agents means child agent execution is completely invisible to parent observability systems. This explains why nested research pipelines do not appear in the UI."

### From Agent 3 (Projects/Sessions)
- System is **session-based, not project-based**
- Sessions tracked by UUID, persist for lifetime of tracker
- Multiple agents in same runtime share session ID but don't track research work as coherent pipeline
- Sessions are ideal for grouping related delegations if we add delegation tracking

### From Agent 5 (Costs)
- Cost tracking **fully working**: costs.jsonl has 50 records spanning 31 days
- Session-scoped aggregation functioning correctly
- **Gap**: No timezone-aware aggregation; no trend analysis

### From Agent 7 (Streaming)
- Response streaming works: 80-char chunks, 50-200ms latency
- Line-buffered pipe from Rust → Python → Streamlit
- **Gap**: Polling mechanism in Streamlit stubbed out (placeholder comments)

### From Agent 8 (Tool Pipeline) - CRITICAL
**Second root cause of missing visibility:**

- Tool execution pipeline is **70% implemented**
- Tools are parsed, executed, results captured
- BUT: Results **never written to `~/.zeroclaw/state/tool_history.jsonl`**
- ObserverEvent has tool name + duration + success only; **missing**: input params, output, approval status
- Python layer ready to read; Rust layer never writes

**Gap Analysis:**
```
Expected (Python ToolExecution dataclass):
- id, tool_name, input_params, output, success, duration_ms, timestamp, 
  approved, approver, danger_level

Actual (Rust ObserverEvent::ToolCall):
- tool, duration, success (3/10 fields = 30% sufficient)
```

### From Agent 10 (Real-Time Data)
**Structural gap in UI architecture:**

- 8 data sources available; only 4 fully utilized
- **Unused data**:
  - `audit.jsonl`: Security audit trail, never accessed
  - `tool_history.jsonl`: Parser exists but file always empty
  - `conversations/`: Multi-session history only partially used
  - `gateway.log`: Never read

- **Mock data fallbacks**:
  - RealTimeMetrics uses synthetic data despite real process metrics available
  - ActivityStream generates fake events despite audit.jsonl existing
  - Analytics charts all synthetic

- **Polling mechanism**:
  - `realtime_poller.py` has placeholder comments, doesn't actually poll
  - Most components refresh only on page load
  - Only `live_metrics.py` has working 5s auto-refresh (but with blocking sleep)

---

## 2. THE COMPLETE DATA FLOW PROBLEM

### What Should Happen (Nested Agent Research)

```
Parent Agent starts
  ↓
User: "Research X and synthesize findings"
  ↓
Parent calls delegate(agent="researcher", prompt="Research X")
  ↓
[THIS IS WHERE VISIBILITY BREAKS]
  ↓
Child Agent (researcher) runs
  - Calls tools (search, file read, etc.)
  - Gets tool results back
  - Calls LLM with results
  - Decides if more research needed
  - Returns findings to parent
  ↓
Parent receives findings
  ↓
Parent delegates to synthesizer: delegate(agent="synthesizer", prompt="Synthesize findings")
  ↓
[AGAIN: COMPLETELY INVISIBLE]
  ↓
Synthesizer runs, returns summary
  ↓
Parent assembles final response to user
```

### What Actually Gets Logged

```
Parent Agent starts
  ↓
[ObserverEvent::AgentStart]
  ↓
User message received
  ↓
LLM called
  ↓
[ObserverEvent::LlmRequest]
[ObserverEvent::LlmResponse]
  ↓
Tool "delegate" executed
  ↓
[ObserverEvent::ToolCall { tool: "delegate", duration: 1500ms, success: true }]
  ↓
[CHILD EXECUTION IS BLACK BOX - NoopObserver discards all events]
  ↓
Result returned to parent
  ↓
Parent assembles response, returns to user
  ↓
[ObserverEvent::TurnComplete]
[ObserverEvent::AgentEnd]

Result: User/UI sees nothing about the research work that happened inside delegate calls
```

---

## 3. FIVE CRITICAL GAPS IDENTIFIED

| Gap | Status | Owner | Impact | Effort |
|-----|--------|-------|--------|--------|
| **No delegation tree tracking** | ❌ | Rust agent | Delegations invisible | 6h |
| **Tool history not persisted** | ❌ | Rust observer | No audit trail | 8h |
| **ObserverEvent insufficient** | ❌ | Rust observability | Missing context | 10h |
| **UI uses mock data** | ❌ | Python UI | Dashboard stale | 8h |
| **Real-time polling stubbed** | ❌ | Python UI | No live updates | 12h |

---

## 4. IMPLEMENTATION ROADMAP

### PHASE 1: Quick Wins (Enable Basic Visibility) - 1-2 Weeks

**Goal**: Make nested delegations at least *visible* in logs and basic UI. Enables data collection for later analysis.

#### 1.1 Add Delegation Events (4-6 hours)

**New events**:
```rust
DelegationStart {
    parent_agent: String,
    child_agent: String,
    depth: u32,
    agentic: bool,
    timestamp: SystemTime,
},
DelegationEnd {
    parent_agent: String,
    child_agent: String,
    depth: u32,
    duration: Duration,
    success: bool,
}
```

**Where**: `src/tools/delegate.rs` (emit at start of execute, end of execute)

#### 1.2 Implement Delegation Logger Observer (6-8 hours)

**New file**: `src/observability/delegation_logger.rs`

**Output**: `~/.zeroclaw/state/delegation_tree.jsonl`

```json
{"event":"delegation_start","parent":"root","child":"researcher","depth":1,"agentic":true,"timestamp":"2026-02-21T10:30:00Z"}
{"event":"delegation_end","parent":"root","child":"researcher","duration_ms":1234,"success":true}
```

#### 1.3 Implement Tool History Writer Observer (8-10 hours)

**New file**: `src/observability/tool_history_writer.rs`

**Output**: `~/.zeroclaw/state/tool_history.jsonl`

**Challenge**: Current `ObserverEvent::ToolCall` lacks input/output. Must:
- Expand event definition OR
- Capture from execution context (requires plumbing)

#### 1.4 Create Python Parsers (4-6 hours)

**New file**: `streamlit-app/lib/delegation_parser.py`
- `read_tree()` → Parse delegation_tree.jsonl
- `get_tree_structure()` → Build nested dict

**New file**: `streamlit-app/lib/audit_parser.py`
- `read_events()` → Parse audit.jsonl (already exists!)

#### 1.5 Add Debug Dashboard (3-4 hours)

**New file**: `streamlit-app/pages/pipeline_debug.py`
- Display delegation tree as JSON
- Show raw delegation events
- Simple text-based, not pretty, but functional

**Purpose**: Immediate feedback that system is tracking delegations

#### 1.6 Configuration Toggle (1-2 hours)

**Add to config.toml**:
```toml
[observability]
backend = "delegation_logger"  # New option
persistence = true            # Enable .jsonl writing
```

#### Phase 1 Summary

| Component | Effort | Status |
|-----------|--------|--------|
| Delegation events | 2h | Ready |
| Delegation logger | 7h | Ready |
| Tool history writer | 9h | Ready |
| Python parsers | 5h | Ready |
| Debug dashboard | 3h | Ready |
| Config | 1h | Ready |
| **TOTAL** | **27 hours** | **1-2 weeks** |

**Deliverables**:
- ✅ Delegation tree logged to JSONL (enables later reconstruction)
- ✅ Tool history written to JSONL (even if partial initially)
- ✅ Debug page showing delegation structure
- ✅ Data pipeline ready for Phase 2 enhancements

---

### PHASE 2: Enhanced Tracking (Persistent Data Infrastructure) - 2-3 Weeks

**Goal**: Capture complete execution context; enable rich analysis.

#### 2.1 Expand ObserverEvent (4-6 hours)

```rust
ObserverEvent::ToolCall {
    id: String,                    // NEW
    tool: String,
    input_params: serde_json::Value,  // NEW
    output: String,                   // NEW
    error: Option<String>,            // NEW
    duration: Duration,
    success: bool,
    timestamp: SystemTime,            // NEW
    parent_agent: Option<String>,     // NEW
    session_id: Option<String>,       // NEW
}
```

**Challenge**: Requires plumbing through execution path to include input/output.

#### 2.2 Create ToolExecutionRecord (3-4 hours)

**New file**: `src/tools/execution.rs`

Schema compatible with Python ToolExecution dataclass:
```rust
pub struct ToolExecutionRecord {
    pub id: String,
    pub session_id: String,
    pub parent_agent: Option<String>,
    pub depth: u32,
    pub tool_name: String,
    pub input_params: serde_json::Value,
    pub output: String,
    pub error: Option<String>,
    pub success: bool,
    pub duration_ms: f64,
    pub timestamp: DateTime<Utc>,
    pub approval_status: Option<String>,
    pub danger_level: String,
}
```

#### 2.3 Research Session Mapping (6-8 hours)

**New file**: `src/cost/research_session.rs`

**Output**: `~/.zeroclaw/state/research_sessions.jsonl`

Maps session_id → root_agent → delegation_tree → tool_executions → costs

#### 2.4 Approval Integration (5-7 hours)

Link Python approval system with Rust events.

**Output**: `~/.zeroclaw/state/approvals.jsonl`

#### 2.5 Research Browser UI (8-10 hours)

**New file**: `streamlit-app/pages/research_browser.py`

Features:
- Session selector
- Delegation tree display
- Tool execution timeline
- Cost breakdown
- Session analytics

#### Phase 2 Summary

| Component | Effort | Status |
|-----------|--------|--------|
| Expand events | 5h | Ready |
| ToolExecutionRecord | 4h | Ready |
| Research session mapping | 7h | Ready |
| Approval integration | 6h | Ready |
| Research browser UI | 9h | Ready |
| **TOTAL** | **31 hours** | **2-3 weeks** |

**Deliverables**:
- ✅ Complete tool history with input/output/approval
- ✅ Research sessions linked to costs and delegations
- ✅ Research browser page showing nested pipelines
- ✅ Historical analysis of agent research work

---

### PHASE 3: Advanced Visualizations (Interactive UI) - 3-4 Weeks

**Goal**: Interactive visualization of nested research pipelines.

#### 3.1 Interactive Pipeline Tree

- Clickable nodes (expand/collapse)
- Hover tooltips (execution details)
- Color-coded by status (running/success/failed)
- Cost overlay on nodes

#### 3.2 Real-Time Delegation Streaming

- WebSocket or SSE for live updates
- Streaming tool executions
- Real-time cost accumulation

#### 3.3 Research Analytics Dashboard

- Delegation branching analysis
- Tool utilization by agent
- Cost per research session
- Time-to-completion trends

#### 3.4 Approval Queue UI

- Pending approvals with context
- Approval decision panel
- Audit trail of approvals

---

## 5. QUICK WIN ACTIONS FOR IMMEDIATE IMPROVEMENT

### For Developers (Day 1)

1. **Enable logging in config**:
```toml
[observability]
backend = "log"
persistence = true
```

2. **Check delegation visibility**:
```bash
tail -f ~/.zeroclaw/state/delegation_tree.jsonl
```

3. **Run agent with delegation**:
```bash
zeroclaw chat "Please research X and synthesize" --model anthropic/claude-sonnet-4
```

### For Streamlit UI (Week 1)

1. **Add Audit Log Visualization** (2-3 hours)
   - Parse `audit.jsonl`
   - Display in dashboard
   - Data already exists, just needs UI

2. **Replace Mock Data** (3-4 hours)
   - Replace synthetic data with real process/cost data
   - Update RealTimeMetrics, ActivityStream
   - High impact on UI credibility

3. **Enable Cost Auto-Refresh** (1 hour)
   - Move CostTracking to 2s polling
   - Use existing costs_parser
   - Immediate UX improvement

4. **Fix Blocking Sleep** (1-2 hours)
   - Replace `time.sleep(5)` in live_metrics.py
   - Use session state timestamps
   - Unlock UI responsiveness

---

## 6. SUCCESS CRITERIA

### Phase 1 (Minimum Viable Delegation Visibility)
- ✅ Delegation events logged to JSONL
- ✅ Tool history written to JSONL (at least success/failure)
- ✅ Debug page shows delegation structure
- ✅ Data collection infrastructure ready

### Phase 2 (Complete Research Session Tracking)
- ✅ Tool execution records with full context
- ✅ Research sessions linked to costs
- ✅ Research browser page functional
- ✅ Multi-session analysis possible

### Phase 3 (Production-Ready Visualization)
- ✅ Interactive pipeline visualization
- ✅ Real-time updates
- ✅ Analytics dashboard
- ✅ User can explore nested research work visually

---

## 7. EFFORT ESTIMATE

| Phase | Rust | Python | UI | Testing | Total | Weeks |
|-------|------|--------|-----|---------|--------|-------|
| **1** | 8h | 8h | 4h | 2h | 22h | 1-2w |
| **2** | 20h | 15h | 10h | 5h | 50h | 2-3w |
| **3** | 5h | 10h | 20h | 5h | 40h | 3-4w |
| **TOTAL** | **33h** | **33h** | **34h** | **12h** | **112h** | **6-9 weeks** |

**Cost**: ~$150/hour × 112 hours = ~$16,800

---

## 8. CRITICAL PATH

```
Phase 1a: Delegation events → Phase 1b: Delegation logger → Phase 1c-e: Parallel
    ↓
Phase 2: Expand events + storage
    ↓
Phase 3: Interactive UI
```

No hard blockers; can start Phase 1 immediately.

---

## 9. ROLLBACK STRATEGIES

### Phase 1: LOW RISK
- Remove config option
- Delete new observer backends
- All backward compatible

### Phase 2: MEDIUM RISK
- Revert ObserverEvent changes (breaking to custom observers)
- Delete new .jsonl files
- Reverting restores pre-Phase-2 behavior

### Phase 3: LOW RISK
- UI-only changes
- Revert pages/components
- Backend unaffected

---

## 10. CONCLUSION

### The Core Problem
User cannot see nested agent research pipelines because:
1. Child agents execute silently (`NoopObserver`)
2. Tool history never persisted
3. Delegation relationships not tracked
4. UI shows mock data instead of real execution

### The Solution
Three-phase implementation:
1. **Phase 1**: Log delegations + tool history (makes system visible)
2. **Phase 2**: Capture full context + create research sessions (enables analysis)
3. **Phase 3**: Interactive visualization (enables exploration)

### Immediate Next Steps
1. Implement Phase 1 (27 hours, 1-2 weeks)
2. Deploy debug dashboard (immediate user feedback)
3. Begin Phase 2 work (2-3 weeks)

### Success Metric
**User can start a nested agent research task and see:**
- Live delegation tree in dashboard
- Tool executions per agent
- Real-time cost accumulation
- Historical analysis of research sessions

---

## APPENDIX: Files to Create/Modify

### Rust Files
**Create**:
- `src/observability/delegation_logger.rs`
- `src/observability/tool_history_writer.rs`
- `src/tools/execution.rs`
- `src/cost/research_session.rs`
- `src/security/approval_tracker.rs`

**Modify**:
- `src/observability/traits.rs` (add events)
- `src/tools/delegate.rs` (emit events)
- `src/observability/mod.rs` (factory)
- `src/config/schema.rs` (config)

### Python Files
**Create**:
- `streamlit-app/lib/delegation_parser.py`
- `streamlit-app/lib/audit_parser.py`
- `streamlit-app/lib/research_session_manager.py`
- `streamlit-app/pages/pipeline_debug.py`
- `streamlit-app/pages/research_browser.py`

**Modify**:
- `streamlit-app/components/dashboard/live_metrics.py` (fix sleep)
- `streamlit-app/pages/dashboard.py` (replace mock data)

---

**Master Report Completed**: 2026-02-21  
**Synthesized By**: Agent 12  
**Recommended First Action**: Begin Phase 1 implementation  
**Estimated Delivery**: 6-9 weeks for complete solution
