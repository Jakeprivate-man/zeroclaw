# Agent 03 Investigation: Quick Reference

## Key Finding

**ZeroClaw is SESSION-BASED, not PROJECT-BASED**

---

## What Exists

✅ **Sessions** (UUID-based)
- Created on agent startup
- Tracked in `~/.zeroclaw/state/costs.jsonl`
- Lifetime: Application instance lifecycle (hours to days)
- Grouped by: `session_id` field

✅ **Multi-Agent Coordination**
- Shared memory store (SQLite/Postgres)
- Optional session filtering
- Cron jobs for task orchestration
- Gateway webhooks for triggering

---

## What Does NOT Exist

❌ **Projects** (as first-class concept)
- No `struct Project` in codebase
- No project creation/management APIs
- No dedicated project storage
- Would need to be implemented at UI layer

---

## Session Data Model (JSONL)

```json
{
  "id": "cost-record-uuid",
  "session_id": "session-uuid",
  "model": "anthropic/claude-sonnet-4",
  "input_tokens": 2537,
  "output_tokens": 1475,
  "cost_usd": 0.029736,
  "timestamp": "2026-01-21T10:37:08.529651Z"
}
```

**Key Field**: `session_id` (primary grouping key)

---

## Real-World Sessions

| Session | Records | Duration | Cost | Models |
|---------|---------|----------|------|--------|
| A | 16 | 13 days | $0.40 | 4 models |
| B | 9 | 23 days | $0.25 | 3 models |
| C | 25 | 30 days | $0.68 | 4 models |

---

## Multi-Agent Coordination Pattern

```
Agent 1 → Store Memory (session-scoped or global)
Agent 2 → Query Memory (retrieves from shared store)
Agent 3 → Cron Job (runs on Main or Isolated session)
```

**Shared Resource**: Memory backend (Arc<dyn Memory>)

---

## How to Implement Projects

1. **Short-term**: Use sessions as project proxies in UI
2. **Medium-term**: Create `projects` table, link session_ids
3. **Long-term**: Consider workspace isolation per project

---

## Files to Know

| File | Purpose |
|------|---------|
| `src/cost/tracker.rs` | Session tracking, cost aggregation |
| `src/cost/types.rs` | CostRecord schema |
| `src/memory/traits.rs` | Memory trait (session-scoped) |
| `src/agent/agent.rs` | Agent initialization, shared memory |
| `src/cron/types.rs` | Cron jobs, SessionTarget (Main/Isolated) |
| `~/.zeroclaw/state/costs.jsonl` | Real session/cost data |

---

## Quick Facts

- Session ID: Generated once per `CostTracker` instance
- Memory: Optional session filtering via `session_id: Option<&str>`
- Cron Jobs: Can target `SessionTarget::Main` (shared) or `SessionTarget::Isolated`
- Cost Tracking: Per-session total + daily/monthly global
- Progress: Via `CronRun` records + cost summaries

---

**Report**: `/Users/jakeprivate/zeroclaw/AGENT_03_PROJECTS_REPORT.md`  
**Investigation Date**: 2026-02-21  
**Status**: Complete

