# Agent 04 Investigation: Token Counting & Cost Calculation Pipeline

**Investigation Date**: February 21, 2026  
**Investigator**: Agent 4 (File Search Specialist)  
**Status**: COMPLETE - CRITICAL FINDINGS IDENTIFIED

---

## Executive Summary

ZeroClaw has a **complete but DISCONNECTED cost tracking infrastructure**. The codebase defines comprehensive token counting and cost calculation systems, but they are **NOT WIRED INTO THE RUNTIME**. The infrastructure exists only in tests; no actual token recording occurs in production.

**Critical Finding**: There is **NO per-agent token attribution** capability at all—neither session-level nor per-agent. The delegation system creates nested agents but does not track which costs belong to which agent in the tree.

---

## 1. Token Counting Pipeline

### 1.1 TokenUsage Struct Definition

**Location**: `/Users/jakeprivate/zeroclaw/src/cost/types.rs:3-61`

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenUsage {
    pub model: String,                          // e.g., "anthropic/claude-sonnet-4-20250514"
    pub input_tokens: u64,                      // Prompt/request tokens
    pub output_tokens: u64,                     // Completion/response tokens
    pub total_tokens: u64,                      // input + output
    pub cost_usd: f64,                          // Calculated cost in USD
    pub timestamp: chrono::DateTime<chrono::Utc>, // Request timestamp
}
```

**Key Implementation**:
- Cost calculation: `(input_tokens / 1M) * input_price_per_million + (output_tokens / 1M) * output_price_per_million`
- Price sanitization prevents NaN/infinite costs
- Created via `TokenUsage::new(model, input, output, input_price_per_million, output_price_per_million)`

### 1.2 Cost Record Schema

**Location**: `/Users/jakeprivate/zeroclaw/src/cost/types.rs:71-91`

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostRecord {
    pub id: String,              // UUID
    pub usage: TokenUsage,       // Complete token usage details
    pub session_id: String,      // Session grouping (NOT agent-specific)
}
```

**Critical Limitation**: The `CostRecord` contains **ONLY `session_id`, not `agent_id`**. There is no field for:
- Agent name/identifier
- Delegation depth
- Parent agent ID
- Tool context

### 1.3 Actual costs.jsonl Format

**Location**: `/Users/jakeprivate/.zeroclaw/state/costs.jsonl` (sample data)

```json
{
  "id": "2fe9e123-09a0-4b5a-a187-104d253d6820",
  "session_id": "b9b607f9-eb13-4302-94ae-61ecbdbf2c97",
  "model": "anthropic/claude-sonnet-4",
  "input_tokens": 2537,
  "output_tokens": 1475,
  "total_tokens": 4012,
  "cost_usd": 0.029736,
  "timestamp": "2026-01-21T10:37:08.529651Z"
}
```

**Issue**: The stored JSON flattens TokenUsage fields directly, but still only groups by `session_id`. No agent attribution.

---

## 2. Cost Calculation Pipeline

### 2.1 Cost Calculation Logic

**Location**: `/Users/jakeprivate/zeroclaw/src/cost/types.rs:29-55`

```rust
pub fn new(
    model: impl Into<String>,
    input_tokens: u64,
    output_tokens: u64,
    input_price_per_million: f64,
    output_price_per_million: f64,
) -> Self {
    let input_cost = (input_tokens as f64 / 1_000_000.0) * input_price_per_million;
    let output_cost = (output_tokens as f64 / 1_000_000.0) * output_price_per_million;
    let cost_usd = input_cost + output_cost;
    // ...
}
```

**Current State**:
- Prices are stored as "per million tokens"
- No pricing table found in codebase
- Prices are passed at TokenUsage creation time (caller responsible)
- No hardcoded model → price mapping

### 2.2 Budget Enforcement

**Location**: `/Users/jakeprivate/zeroclaw/src/cost/tracker.rs:50-107`

The `CostTracker` supports:
- Daily budget limits (checked against `costs.jsonl`)
- Monthly budget limits
- Warning threshold (% of limit)
- Per-request budget pre-check

**Code Flow**:
1. `check_budget(estimated_cost)` queries persistent storage
2. Aggregates costs from JSONL by date/month
3. Returns `BudgetCheck::Allowed`, `::Warning`, or `::Exceeded`

---

## 3. Storage Pipeline (JSONL Write Path)

### 3.1 Persistent Storage Implementation

**Location**: `/Users/jakeprivate/zeroclaw/src/cost/tracker.rs:228-402`

The `CostStorage` struct manages the JSONL file:

```rust
fn add_record(&mut self, record: CostRecord) -> Result<()> {
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&self.path)?;
    
    writeln!(file, "{}", serde_json::to_string(&record)?)?;
    file.sync_all()?;  // Durability guarantee
    // ...
}
```

**Path Resolution**:
```
workspace_dir / "state" / "costs.jsonl"
(e.g., ~/.zeroclaw/state/costs.jsonl)
```

Fallback migration from legacy `.zeroclaw/costs.db` supported.

### 3.2 Full Record Structure Written to JSONL

Each line is a serialized `CostRecord`:
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "usage": {
    "model": "string",
    "input_tokens": u64,
    "output_tokens": u64,
    "total_tokens": u64,
    "cost_usd": f64,
    "timestamp": "ISO-8601"
  }
}
```

(Actually flattened in storage, not nested.)

---

## 4. Attribution Analysis - THE CRITICAL GAP

### 4.1 Session-Level Attribution Only

Current implementation:
- All costs in a runtime session share ONE `session_id` (UUID)
- Generated once per `CostTracker` instance: `let session_id = uuid::Uuid::new_v4().to_string()`
- Costs are grouped by `session_id` in summaries

**What EXISTS**:
- Summary by model (`by_model: HashMap<String, ModelStats>`)
- Summary by time period (day, month)
- Summary by session

**What DOES NOT EXIST**:
- Per-agent cost tracking
- Per-delegation-depth cost tracking
- Tool-specific cost attribution
- Nested agent cost separation

### 4.2 Delegation Tool Architecture

**Location**: `/Users/jakeprivate/zeroclaw/src/tools/delegate.rs`

The delegation system creates **nested sub-agents** but has **NO cost tracking for sub-agent calls**:

```rust
pub struct DelegateTool {
    agents: Arc<HashMap<String, DelegateAgentConfig>>,
    security: Arc<SecurityPolicy>,
    depth: u32,  // Recursion depth tracking EXISTS
    parent_tools: Arc<Vec<Arc<dyn Tool>>>,
    // NO agent_id, NO cost_tracker
}
```

**Two Execution Paths**:

1. **Simple Mode** (one-shot call):
   ```rust
   provider.chat_with_system(system, prompt, model, temp).await
   ```
   - Creates tokens in sub-agent's model
   - Tokens are NOT tracked separately
   - All costs roll up to parent session_id

2. **Agentic Mode** (full tool loop):
   ```rust
   run_tool_call_loop(provider, history, tools, noop_observer, ...)
   ```
   - Sub-agent iterates with tools
   - Uses `NoopObserver` (ignores all events)
   - Tokens consumed by sub-agent tools NOT ATTRIBUTED TO SUB-AGENT

### 4.3 The Disconnect: CostTracker Exists But Is NOT USED

**Search Result**: No production use of `CostTracker` or `TokenUsage` outside test code.

```bash
$ grep -r "record_usage\|TokenUsage::new\|CostTracker::new" src --include="*.rs" \
  | grep -v "cost/tracker.rs" | grep -v "cost/types.rs" | grep -v "#\[test"
# Returns: NOTHING
```

**What This Means**:
- No code path calls `cost_tracker.record_usage()`
- No provider integration records token counts
- The 50-line sample in `costs.jsonl` is fixture data, not runtime data
- The infrastructure is **complete but unreachable from the runtime**

---

## 5. Token Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ USER MESSAGE                                                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        ┌─────────────────────────┐
        │ Agent Loop (loop_.rs)   │
        │ - chat_with_history()   │
        │ - tool dispatch         │
        └────────────┬────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
    [Provider API]      [Delegate Tool]
    (Anthropic,          (Sub-agent)
     OpenAI, etc.)        |
          │               ├─ depth tracking ✓
          │               ├─ NO cost tracking ✗
          │               └─ Recursive tool loop
          │
          ▼ (TOKENS CONSUMED HERE - NOT RECORDED)
    
    ┌──────────────────────────────────────────┐
    │ TokenUsage COULD BE CREATED              │
    │ - Model: identified                      │
    │ - Input/output tokens: available         │
    │ - Cost: calculable                       │
    │ - But NO CODE CALLS .record_usage()      │
    └──────┬───────────────────────────────────┘
           │
           X NO INTEGRATION POINT ✗
           │
           ▼ (DEAD CODE PATH)
    
    ┌──────────────────────────────────────────┐
    │ CostTracker.record_usage()               │
    │ - Validates cost                         │
    │ - Creates CostRecord                     │
    │ - Writes to costs.jsonl                  │
    │ [UNREACHABLE FROM RUNTIME]               │
    └──────┬───────────────────────────────────┘
           │
           ▼ (TESTS ONLY)
    
    ~/.zeroclaw/state/costs.jsonl
    [Contains sample fixture data, not actual costs]
```

---

## 6. Configuration

### 6.1 CostConfig Schema

**Location**: `/Users/jakeprivate/zeroclaw/src/config/schema.rs`

```rust
pub struct CostConfig {
    pub enabled: bool,                      // Default: false
    pub daily_limit_usd: f64,              // Default: 10.00
    pub monthly_limit_usd: f64,            // Default: 100.00
    pub warn_at_percent: u32,              // Default: 80
}
```

**Current State**: Cost tracking is **DISABLED BY DEFAULT** and has **NO PRODUCTION WIRING**.

### 6.2 Budget Check Integration

The only place `CostConfig` is referenced in main code:
```rust
// src/main.rs
let max_cost_per_day = f64::from(config.autonomy.max_cost_per_day_cents) / 100.0
```

This reads from `autonomy.max_cost_per_day_cents`, NOT from the cost tracker.

---

## 7. Critical Gaps & Implications

### 7.1 Immediate Gaps

| Gap | Impact | Severity |
|-----|--------|----------|
| **No Runtime Integration** | Token usage is NEVER recorded, even when enabled | CRITICAL |
| **No Per-Agent Attribution** | Cannot see which agent/tool consumed tokens | CRITICAL |
| **No Provider Hook** | Providers don't extract or report token usage | HIGH |
| **No Delegation Tracking** | Nested agents roll costs into parent session | HIGH |
| **No Pricing Table** | No model → price mapping (caller must provide) | MEDIUM |
| **Sample Data in JSONL** | Existing costs.jsonl contains fixture data | MEDIUM |

### 7.2 For the Token Research UI

**Current State**: There is **NO DATA** to display per-agent token usage because:
1. Tokens are never counted in runtime
2. No agent ID is stored even if they were counted
3. Delegation tree has no cost boundaries
4. Session-level costs exist but can't be subdivided by agent

**What Would Be Required**:
1. Integrate provider token responses into CostRecord
2. Add `agent_id` and `delegation_depth` fields to CostRecord
3. Modify delegation tool to create child CostTracker instances
4. Hook CostTracker.record_usage() into agent loop after each provider call
5. Expose per-agent cost summaries in API

---

## 8. Cost Record Fields (Complete Schema)

**As Currently Stored** (flattened in JSONL):
```json
{
  "id": "string (UUID)",
  "session_id": "string (UUID)",
  "model": "string",
  "input_tokens": "u64",
  "output_tokens": "u64",
  "total_tokens": "u64",
  "cost_usd": "f64",
  "timestamp": "string (ISO-8601)"
}
```

**Missing Fields for Per-Agent Tracking**:
- `agent_id`: Which agent made this request
- `agent_name`: Friendly name (for UI)
- `delegation_depth`: How nested in delegation tree
- `parent_agent_id`: Parent in tree (for hierarchy)
- `tool_name`: Which tool triggered the request (if any)
- `request_type`: "chat" | "delegate" | "completion"
- `session_cost_attribution`: Portion of session budget used (for accounting)

---

## 9. Test Evidence

All evidence of token tracking is in test code only:

**File**: `/Users/jakeprivate/zeroclaw/src/cost/tracker.rs:405-536`

Tests confirm the infrastructure works:
- `cost_tracker_initialization()` ✓
- `record_usage_and_get_summary()` ✓
- `budget_exceeded_daily_limit()` ✓
- `summary_by_model_is_session_scoped()` ✓
- `malformed_lines_are_ignored_while_loading()` ✓

But there are **ZERO** tests showing CostTracker being instantiated or used in the agent loop.

---

## 10. Findings Summary

### What IS Implemented ✓

1. **Token counting struct** (`TokenUsage`)
2. **Cost calculation** (tokens × price per million)
3. **Persistent storage** (JSONL with sync guarantees)
4. **Budget enforcement** (daily/monthly checks)
5. **Aggregation queries** (by date, model, session)
6. **Delegation depth tracking** (depth field in DelegateTool)

### What IS NOT Implemented ✗

1. **Provider integration** - No code extracts tokens from API responses
2. **Runtime wiring** - No code calls `record_usage()`
3. **Agent attribution** - No `agent_id` in CostRecord
4. **Sub-agent cost tracking** - Delegate tool has no cost isolation
5. **Cost summary by agent** - Cannot drill down per agent
6. **Configuration handling** - CostConfig exists but is never instantiated
7. **Pricing table** - Model prices are not defined anywhere

---

## 11. Recommendations for Token Research Pipeline

### Phase 1: Enable Infrastructure
- [ ] Instantiate `CostTracker` in agent initialization
- [ ] Create provider hooks to extract token usage from responses
- [ ] Add `record_usage()` calls after each provider API call
- [ ] Add `agent_id` / `delegation_depth` to `CostRecord` struct
- [ ] Update costs.jsonl schema with new fields (with migration)

### Phase 2: Per-Agent Tracking
- [ ] Create child CostTracker instances for delegated sub-agents
- [ ] Track cost attribution in delegation tree
- [ ] Implement per-agent cost summary queries
- [ ] Store parent-child relationships in CostRecord

### Phase 3: UI Exposure
- [ ] Add `/api/costs/by-agent` endpoint
- [ ] Add `/api/costs/by-model` endpoint
- [ ] Add `/api/costs/timeline` endpoint
- [ ] Expose delegation tree with per-node costs
- [ ] Add cost breakdown widget to UI

---

## 12. Code Locations Reference

| Component | File | Lines | Status |
|-----------|------|-------|--------|
| TokenUsage | `src/cost/types.rs` | 3-61 | ✓ Implemented |
| CostRecord | `src/cost/types.rs` | 71-91 | ✓ Implemented (incomplete schema) |
| CostTracker | `src/cost/tracker.rs` | 12-176 | ✓ Implemented (unused) |
| CostStorage | `src/cost/tracker.rs` | 228-402 | ✓ Implemented (unused) |
| CostConfig | `src/config/schema.rs` | (various) | ✓ Defined (not wired) |
| DelegateTool | `src/tools/delegate.rs` | 19-1094 | ⚠ Has depth tracking, no cost tracking |
| Agent Loop | `src/agent/loop_.rs` | (full) | ✗ No cost tracking calls |
| costs.jsonl | `~/.zeroclaw/state/` | (JSONL) | ✗ Contains fixture data only |

---

## Conclusion

ZeroClaw has built a **complete, well-designed token counting and cost calculation system** but left it **completely disconnected from the runtime**. The delegation system tracks recursion depth but not costs. There is **no per-agent attribution capability** at all—the infrastructure only supports session-level summaries, and even those aren't actually populated.

**To enable token research visibility per agent, a significant integration effort is required** to:
1. Connect providers to cost tracking
2. Add agent/depth fields to records
3. Extend delegation to track sub-agent costs separately
4. Expose aggregated costs through the API

The infrastructure provides a solid foundation, but the "last mile" of production integration is completely missing.

