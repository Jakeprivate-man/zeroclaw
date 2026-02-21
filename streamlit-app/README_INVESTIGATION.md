# ZeroClaw Agent Runtime Investigation - Complete

## Investigation Complete ✓

Comprehensive investigation of the ZeroClaw agent runtime architecture is complete. Three detailed deliverables have been created:

### Deliverables

1. **ZEROCLAW_ARCHITECTURE_INVESTIGATION.md** (38KB, 1121 lines)
   - Complete architecture map of all core systems
   - Detailed explanation of research tokens (cost tracking)
   - Gateway API inventory with examples
   - UI requirements and priorities
   - Implementation notes and critical caveats

2. **INVESTIGATION_SUMMARY.txt** (Quick Reference)
   - Key findings in concise format
   - 10 critical UI gaps identified
   - New API endpoints needed
   - Architecture files to review
   - Next steps checklist

3. **IMPLEMENTATION_ROADMAP.md** (Detailed Phases)
   - Phase 1: Cost & Token Tracking (CRITICAL)
   - Phase 2: Agent Orchestration & Tools (HIGH PRIORITY)
   - Phase 3: Model Selection & Multi-Agent (IMPORTANT)
   - Phase 4: Memory & Gateway Config (NICE-TO-HAVE)
   - Phase 5: Advanced Analytics (OPTIONAL)
   - Resource allocation and risk assessment

---

## Key Findings

### 1. "Research Tokens" Definition

**Finding:** No discrete "research token" concept exists in ZeroClaw.

**Reality:** Comprehensive TokenUsage tracking system that monitors:
- Input tokens (prompt)
- Output tokens (completion)
- Total tokens
- Cost in USD (calculated per model)
- Timestamp of each request

Storage: JSONL file at `~/.zeroclaw/state/costs.jsonl` (one record per API call)

### 2. Cost Tracking System

The runtime includes a sophisticated cost management system:
- **CostTracker** class manages all token/cost tracking
- **Budget enforcement** with daily/monthly limits
- **Warning thresholds** (e.g., warn at 80%)
- **Per-model pricing** database (100+ models hardcoded)
- **Session aggregation** (current session costs)

### 3. Multi-Agent Support

ZeroClaw supports sophisticated multi-agent workflows via **DelegateTool**:
- Sub-agent specialization (different models/providers per agent)
- Depth limiting (prevents infinite delegation loops)
- Tool inheritance (safe subset of tools for sub-agents)
- Timeout enforcement (120-300s per sub-agent)
- Cost rollup (sub-agent costs aggregate to parent)

### 4. Gateway API

Built on **Axum** (Rust async web framework):
- Current endpoints: `/health`, `/metrics`, `/pair`, `/webhook`, `/whatsapp`, `/linq`
- Security: Rate limiting, pairing, idempotency, secret hashing
- Missing endpoints: `/api/cost-summary`, `/api/agents`, `/api/tools`, `/api/memory`

### 5. Rich Tool Ecosystem

30+ executable tools across categories:
- System: shell, browser, screenshot
- Files: read, write, git operations
- Memory: store, recall, forget
- Information: web search, HTTP, image analysis
- Scheduling: cron jobs, one-time schedules
- Hardware: board info, memory read
- Integrations: Composio, Pushover, delegation

### 6. Observability

Multiple real-time backends:
- Prometheus (metrics exposition)
- OpenTelemetry (distributed tracing)
- Log (structured logging)
- Verbose (debug output)

---

## Critical UI Gaps (10 Items)

### Phase 1 - MUST HAVE
1. Cost tracking display (session/daily/monthly USD)
2. Token usage monitoring (input/output per request)
3. Budget status display (% of limit)
4. Budget enforcement UI (alerts at thresholds)
5. Agent status monitor (current agent, available agents)

### Phase 2 - IMPORTANT
6. Tool execution history (searchable)
7. Model/provider selector (quick-switch)
8. Agent orchestration visualizer (delegation tree)
9. Memory recall interface
10. Webhook testing + pairing management

---

## Implementation Priority

### PHASE 1 (1-2 weeks) - CRITICAL
**Focus:** Cost & Token Tracking

Rust backend:
- Add `/api/cost-summary` endpoint
- Add `/api/budget-check` endpoint

Streamlit:
- Extend API client with new methods
- Create Cost Dashboard component
- Add budget alerts

**Estimated Effort:** 14-16 hours

### PHASE 2 (2-3 weeks) - HIGH PRIORITY
**Focus:** Agent Orchestration & Tools

Rust backend:
- Add `/api/agents` endpoint
- Add `/api/tool-executions` endpoint

Streamlit:
- Agent status panel
- Tool execution history table
- Tool timeline chart

**Estimated Effort:** 16-20 hours

### PHASE 3 (2-3 weeks) - IMPORTANT
**Focus:** Model Selection & Multi-Agent

Rust backend:
- Add `/api/models` endpoint

Streamlit:
- Model selector component
- Delegation tree visualizer

**Estimated Effort:** 15-18 hours

---

## New Gateway API Endpoints Needed

```
Cost Tracking:
  GET /api/cost-summary        -> CostSummary
  GET /api/budget-check        -> BudgetCheckResponse

Agent Management:
  GET /api/agents              -> Vec<AgentInfo>
  GET /api/agents/{name}       -> AgentInfo

Tool Execution:
  GET /api/tool-executions     -> Vec<ToolExecution> (paginated)

Memory Operations:
  GET /api/memory              -> Vec<MemoryEntry>
  POST /api/memory             -> MemoryEntry
  DELETE /api/memory/{key}     -> bool
  POST /api/memory/recall      -> Vec<MemoryEntry>

Model/Provider:
  GET /api/models              -> Vec<ModelInfo>

Gateway Config:
  GET /api/gateway/pairing-status  -> PairingStatus
  GET /api/gateway/config          -> GatewayConfig
```

---

## Architecture Files to Reference

**Core Agent System:**
- `/Users/jakeprivate/zeroclaw/src/agent/agent.rs` - Agent structure
- `/Users/jakeprivate/zeroclaw/src/agent/loop_.rs` - Agent execution loop
- `/Users/jakeprivate/zeroclaw/src/agent/dispatcher.rs` - Tool call dispatching

**Cost Tracking:**
- `/Users/jakeprivate/zeroclaw/src/cost/types.rs` - TokenUsage, CostSummary, BudgetCheck
- `/Users/jakeprivate/zeroclaw/src/cost/tracker.rs` - CostTracker implementation

**Gateway:**
- `/Users/jakeprivate/zeroclaw/src/gateway/mod.rs` - HTTP gateway (Axum)

**Multi-Agent:**
- `/Users/jakeprivate/zeroclaw/src/tools/delegate.rs` - DelegateTool
- `/Users/jakeprivate/zeroclaw/src/config/schema.rs` - DelegateAgentConfig

**Observability:**
- `/Users/jakeprivate/zeroclaw/src/observability/mod.rs` - Observer backends

**Memory:**
- `/Users/jakeprivate/zeroclaw/src/memory/traits.rs` - Memory trait

---

## Next Steps

1. **Read Full Investigation**
   - Open `ZEROCLAW_ARCHITECTURE_INVESTIGATION.md`
   - Review all sections for detailed context
   - Check section 11.1 for new API endpoint examples

2. **Review Quick Reference**
   - Use `INVESTIGATION_SUMMARY.txt` for quick lookups
   - Reference file map when exploring codebase

3. **Plan Implementation**
   - Follow `IMPLEMENTATION_ROADMAP.md`
   - Start with Phase 1 (cost tracking)
   - Use checklist to track progress

4. **Review Existing UI**
   - Check what's in `/components/dashboard/`
   - Review `/lib/api_client.py` for existing methods
   - Test current Streamlit UI with mock data

5. **Begin Phase 1 Implementation**
   - Start with gateway API endpoints
   - Then extend Streamlit API client
   - Finally build UI components

---

## Key Technical Notes

### Cost Tracking Integration

- CostTracker is already initialized in gateway (check AppState)
- If not, you'll need to inject it into the gateway
- Cost records stored in JSONL (one per API call)
- Budget enforcement happens before API calls (prevents overage)
- Daily/monthly costs cached but refreshed on date change

### Real-Time Updates

- Current approach: Streamlit polling
- Use 5-10 second refresh intervals (acceptable)
- Alternative: WebSocket/SSE for better performance (Axum supports)
- Consider caching in gateway to avoid repeated file I/O

### Security Considerations

- Never expose raw API tokens in UI
- Hash secrets using SHA256 (never plaintext)
- Enforce rate limiting per IP
- Validate idempotency keys
- Scrub credentials from tool output (already done in agent loop)

---

## Testing Recommendations

### Unit Tests (Rust)
- Test CostTracker access from gateway
- Test endpoint JSON serialization
- Test error handling

### Integration Tests (Python)
- Test API client against live gateway
- Test Streamlit component rendering
- Test error scenarios

### E2E Tests
- Run real agent workflows
- Monitor costs in Streamlit
- Verify budget enforcement
- Check real-time updates

---

## Related Documentation

- `ZEROCLAW_ARCHITECTURE_INVESTIGATION.md` - Full investigation (38KB)
- `INVESTIGATION_SUMMARY.txt` - Quick reference (3KB)
- `IMPLEMENTATION_ROADMAP.md` - Detailed phases and effort estimates
- `/Users/jakeprivate/zeroclaw/CLAUDE.md` - ZeroClaw engineering protocol
- `/Users/jakeprivate/zeroclaw/README.md` - ZeroClaw project overview

---

## Questions & Clarifications

### Q: What are "research tokens"?
**A:** There's no discrete "research token" concept. Instead, ZeroClaw tracks all token usage (input/output) per API call, calculates USD cost using per-model pricing, and enforces daily/monthly budgets.

### Q: How does multi-agent work?
**A:** Via DelegateTool - agents can delegate subtasks to named sub-agents with different models/providers. Depth limiting prevents infinite loops. Sub-agent costs roll up to parent metrics.

### Q: What about real-time metrics?
**A:** Accessible via `/metrics` endpoint (Prometheus text format). New JSON endpoints needed for Streamlit UI (cost-summary, budget-check, agents, tool-executions, memory, models).

### Q: Is tool execution history logged?
**A:** Currently not. Phase 2 implementation needs to add tracking (either in-memory per session, JSONL file, or memory subsystem).

### Q: How do I know what models are available?
**A:** Provider registry is built into runtime. New `/api/models` endpoint can expose this with pricing and capabilities.

---

## Investigation Metadata

- **Start Date:** 2026-02-21
- **Investigation Type:** Comprehensive Architecture Analysis
- **Thoroughness Level:** Very Thorough
- **Codebase Analyzed:** /Users/jakeprivate/zeroclaw/ (complete Rust runtime)
- **UI Location:** /Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/
- **Key Files Reviewed:** 30+ files across agent, cost, gateway, providers, tools, memory, observability modules
- **Total Time Investment:** ~4 hours investigation + documentation

---

**Investigation Complete - Ready for Development**

All information needed to integrate ZeroClaw's agent runtime into the Streamlit UI has been gathered, analyzed, and documented. Proceed with Phase 1 implementation following the roadmap.

