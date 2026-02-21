# ZeroClaw Streamlit UI - Implementation Roadmap

## Overview

This roadmap prioritizes the integration of ZeroClaw's agent runtime features into the Streamlit UI based on investigation findings and user value.

## Phase 1: Cost & Token Tracking (CRITICAL)

**Timeline:** 1-2 weeks  
**Goal:** Enable real-time cost monitoring and budget enforcement visibility

### Tasks

#### 1.1 Gateway API Extension (Rust backend)

Create new endpoints in `/Users/jakeprivate/zeroclaw/src/gateway/mod.rs`:

```rust
// GET /api/cost-summary
// Returns current CostSummary (session/daily/monthly costs)
async fn handle_cost_summary(State(state): State<AppState>) -> Json<CostSummary>

// GET /api/budget-check
// Returns budget status (Allowed/Warning/Exceeded)
async fn handle_budget_check(State(state): State<AppState>) -> Json<BudgetCheckResponse>
```

**Implementation notes:**
- Inject `CostTracker` into `AppState` (if not already present)
- Call `tracker.get_summary()` and `tracker.check_budget()`
- Return JSON-serialized responses
- Handle errors gracefully (tracker may be disabled)

**Estimated effort:** 2-3 hours

#### 1.2 Streamlit API Client Update

Extend `/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/lib/api_client.py`:

```python
def get_cost_summary(self) -> Dict[str, Any]:
    """Get current cost summary."""
    response = self.session.get(f"{self.base_url}/api/cost-summary", timeout=30)
    return response.json()

def get_budget_status(self) -> Dict[str, Any]:
    """Get budget check status."""
    response = self.session.get(f"{self.base_url}/api/budget-check", timeout=30)
    return response.json()
```

**Estimated effort:** 1 hour

#### 1.3 Cost Dashboard Component

Create `/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/components/dashboard/cost_meter.py`:

```python
import streamlit as st
import plotly.graph_objects as go

def render_cost_meter(api):
    """Display cost metrics with gauges and alerts."""
    try:
        summary = api.get_cost_summary()
        budget_status = api.get_budget_status()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Session cost gauge
            st.metric("Session Cost", f"${summary['session_cost_usd']:.2f}")
        
        with col2:
            # Daily cost with budget bar
            daily = summary['daily_cost_usd']
            limit = summary.get('daily_limit', 10.0)
            pct = (daily / limit * 100) if limit > 0 else 0
            st.metric("Daily Cost", f"${daily:.2f}", f"{pct:.0f}% of ${limit:.2f}")
        
        with col3:
            # Monthly cost
            monthly = summary['monthly_cost_usd']
            limit = summary.get('monthly_limit', 100.0)
            pct = (monthly / limit * 100) if limit > 0 else 0
            st.metric("Monthly Cost", f"${monthly:.2f}", f"{pct:.0f}% of ${limit:.2f}")
        
        # Budget alert
        if budget_status['status'] == 'exceeded':
            st.error(f"Budget exceeded: {budget_status['message']}")
        elif budget_status['status'] == 'warning':
            st.warning(f"Budget warning: {budget_status['message']}")
        
        # Cost breakdown by model
        if 'by_model' in summary:
            st.subheader("Cost Breakdown by Model")
            model_data = summary['by_model']
            # Create pie chart
            labels = list(model_data.keys())
            values = [m['cost_usd'] for m in model_data.values()]
            fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
            st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        st.error(f"Failed to fetch cost data: {e}")
```

**Estimated effort:** 4-5 hours

#### 1.4 Dashboard Integration

Update `/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/pages/dashboard.py` to display cost metrics.

**Estimated effort:** 2 hours

### Acceptance Criteria

- [ ] `/api/cost-summary` endpoint returns valid CostSummary JSON
- [ ] `/api/budget-check` endpoint returns BudgetCheckResponse
- [ ] Streamlit API client can call both endpoints
- [ ] Dashboard displays cost metrics in real-time
- [ ] Budget alerts appear when thresholds exceeded
- [ ] Cost breakdown by model displays correctly

---

## Phase 2: Agent Orchestration & Tool Monitoring (HIGH PRIORITY)

**Timeline:** 2-3 weeks  
**Goal:** Expose agent status and tool execution visibility

### Tasks

#### 2.1 Gateway API Extension: Agent Status

```rust
// GET /api/agents
async fn handle_list_agents(State(state): State<AppState>) -> Json<Vec<AgentInfo>>

// Returns list of configured agents with:
// - name, model, provider
// - status (running/idle/error)
// - tool_count
// - last_activity timestamp
```

**Estimated effort:** 3-4 hours

#### 2.2 Gateway API Extension: Tool Execution History

```rust
// GET /api/tool-executions?limit=100&offset=0
async fn handle_tool_executions(
    Query(params): Query<PaginationParams>,
    State(state): State<AppState>
) -> Json<Vec<ToolExecution>>

// Returns tool call history with:
// - id, name, input_params, output
// - success: bool, duration_ms
// - timestamp
```

**Note:** Requires storing tool execution history (not currently captured). Consider:
1. Store in memory (per-session)
2. Write to JSONL file (like costs)
3. Use memory subsystem

**Estimated effort:** 4-5 hours

#### 2.3 Streamlit Components

Create agent/tool visualization components:
- Agent status panel
- Tool execution history table (searchable, filterable)
- Tool execution timeline chart

**Estimated effort:** 6-8 hours

### Acceptance Criteria

- [ ] `/api/agents` endpoint lists agents with current status
- [ ] `/api/tool-executions` returns paginated tool history
- [ ] Dashboard displays agent status with status indicator
- [ ] Tool history shows recent executions in table format
- [ ] Tool history searchable by tool name
- [ ] Tool execution duration visualized in chart

---

## Phase 3: Model Selection & Multi-Agent Workflows (IMPORTANT)

**Timeline:** 2-3 weeks  
**Goal:** Enable dynamic model switching and agent orchestration visibility

### Tasks

#### 3.1 Gateway API Extension: Model Information

```rust
// GET /api/models
async fn handle_list_models(State(state): State<AppState>) -> Json<Vec<ModelInfo>>

// Returns available models with:
// - id, provider, display_name
// - pricing (input_per_mtok, output_per_mtok)
// - capabilities (tools, vision, streaming, etc.)
```

**Estimated effort:** 3 hours

#### 3.2 Model Selector Component

Create quick-switch UI for model selection:
- Dropdown showing available models
- Current model highlighted
- Model pricing displayed
- Provider icon/badge

**Estimated effort:** 3-4 hours

#### 3.3 Agent Orchestration Visualizer

Create delegation tree visualization:
- Show parent-child agent relationships
- Depth indicator
- Cost contribution per sub-agent
- Status indicators

**Estimated effort:** 6-8 hours

### Acceptance Criteria

- [ ] `/api/models` endpoint returns available models with pricing
- [ ] Model selector component works and updates selected model
- [ ] Delegation tree visualizes multi-agent workflows
- [ ] Sub-agent costs tracked and displayed separately
- [ ] Agent delegation manual trigger available

---

## Phase 4: Memory Management & Gateway Config (NICE-TO-HAVE)

**Timeline:** 1-2 weeks  
**Goal:** Expose memory operations and gateway configuration

### Tasks

#### 4.1 Memory API Endpoints

```rust
// GET /api/memory?category=core&limit=10
// POST /api/memory (store)
// DELETE /api/memory/{key}
// POST /api/memory/recall (semantic search)
```

**Estimated effort:** 4-5 hours

#### 4.2 Gateway Config Endpoints

```rust
// GET /api/gateway/pairing-status
// GET /api/gateway/config
// PATCH /api/gateway/config (update)
```

**Estimated effort:** 3 hours

#### 4.3 UI Components

- Memory recall interface
- Memory store form
- Pairing token display/refresh
- Gateway rate limit status

**Estimated effort:** 6-8 hours

---

## Phase 5: Advanced Analytics & Insights (OPTIONAL)

**Timeline:** 2+ weeks  
**Goal:** Provide actionable insights into agent behavior

### Features

- Cost trend analysis (7/30/90 day graphs)
- Model popularity ranking
- Tool usage frequency
- Response time distribution
- Agent efficiency metrics

**Estimated effort:** 8-10 hours

---

## Implementation Checklist

### Before Starting

- [ ] Review `ZEROCLAW_ARCHITECTURE_INVESTIGATION.md` (full reference)
- [ ] Set up ZeroClaw dev environment locally
- [ ] Run existing Streamlit UI against mock data
- [ ] Verify ZeroClaw gateway is accessible

### Phase 1 Checklist

- [ ] Create `/api/cost-summary` endpoint
- [ ] Create `/api/budget-check` endpoint
- [ ] Extend API client with new methods
- [ ] Create cost meter component
- [ ] Update dashboard to use real data
- [ ] Test with real ZeroClaw instance
- [ ] Document new endpoints

### Testing Strategy

**Unit Tests (Rust):**
- Test CostTracker access from gateway
- Test endpoint response serialization
- Test error handling

**Integration Tests (Python):**
- Test API client against live gateway
- Test Streamlit component data rendering
- Test error scenarios

**E2E Tests:**
- Run real agent workflows
- Monitor costs in Streamlit
- Verify budget enforcement
- Check real-time updates

### Documentation Updates

- [ ] Add `/api/*` endpoint documentation
- [ ] Update API client docstrings
- [ ] Add component usage examples
- [ ] Create troubleshooting guide

---

## Risk Assessment

### High Risk

1. **Cost Tracker Integration**
   - Risk: Cost tracking may be disabled or unavailable
   - Mitigation: Check tracker.config.enabled before use
   - Fallback: Display "Tracking unavailable" message

2. **Real-Time Updates**
   - Risk: Streamlit polling may cause excessive load
   - Mitigation: Use 5-10 second refresh intervals
   - Alternative: Implement WebSocket/SSE for better performance

### Medium Risk

1. **Agent State Tracking**
   - Risk: Current agent state not readily available
   - Mitigation: Add optional state tracking to gateway
   - Alternative: Track via observability backend

2. **Tool Execution History**
   - Risk: Tool executions not currently logged
   - Mitigation: Add event tracking to agent loop
   - Storage: JSONL file or memory subsystem

### Low Risk

1. **Model Information**
   - Already available in provider registry
   - Can be cached in gateway AppState

2. **Budget Status**
   - Already implemented in CostTracker
   - Just need to expose via API

---

## Success Metrics

**Phase 1 Success:**
- Cost metrics displayed and updated in real-time
- Budget alerts working correctly
- UI shows accurate cost breakdown by model

**Phase 2 Success:**
- Agent status visible with last activity
- Tool execution history searchable
- Recent executions visible in timeline

**Phase 3 Success:**
- Model selector functional
- Model switching updates agent immediately
- Delegation tree visualizes multi-agent workflows

**Overall Success:**
- Streamlit UI reflects real agent runtime state
- No manual data entry required
- Real-time metrics updated every 5-10 seconds
- All critical features working end-to-end

---

## Rollout Strategy

### Alpha (Phase 1)
- Deploy cost dashboard to staging
- Test with manual agent runs
- Gather feedback from dev team

### Beta (Phase 1 + 2)
- Add agent orchestration monitoring
- Increase automated testing
- Begin production trials

### GA (Phase 1-3)
- All critical features working
- Comprehensive documentation
- Performance optimized
- Full test coverage

---

## Resource Allocation

**Rust Backend (Gateway API):**
- Phase 1: 5-7 hours
- Phase 2: 7-9 hours
- Phase 3: 6-8 hours
- Phase 4: 7-8 hours

**Python/Streamlit (UI):**
- Phase 1: 6-8 hours
- Phase 2: 8-10 hours
- Phase 3: 9-12 hours
- Phase 4: 6-8 hours

**Total Effort:** 50-70 hours (6-9 person-weeks)

---

## Related Documents

- `ZEROCLAW_ARCHITECTURE_INVESTIGATION.md` - Full architecture details
- `INVESTIGATION_SUMMARY.txt` - Quick reference
- `/Users/jakeprivate/zeroclaw/CLAUDE.md` - ZeroClaw engineering protocol

