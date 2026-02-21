# Agent 05: Cost Tracking Quick Reference

**Full Documentation**: See `AGENT_05_COSTS_REPORT.md` (1015 lines)

## Schema at a Glance

```json
{
  "id": "uuid",                              // Unique record ID
  "session_id": "uuid",                      // Groups related API calls
  "model": "provider/model-name",            // e.g., "anthropic/claude-sonnet-4"
  "input_tokens": 2537,                      // Integer
  "output_tokens": 1475,                     // Integer
  "total_tokens": 4012,                      // input + output
  "cost_usd": 0.029736,                      // 6 decimals at write, 4 in aggregations
  "timestamp": "2026-02-21T10:37:08.529651Z" // UTC with microseconds
}
```

**File**: `~/.zeroclaw/state/costs.jsonl` (JSONL format, one record per line)

## Aggregation Rules

| Dimension | Boundary | Algorithm | Time-Zone Aware? |
|-----------|----------|-----------|-----------------|
| Session | session_id match | Filter records by `session_id`, sum costs/tokens | N/A |
| Daily | UTC midnight | `timestamp >= today_start` where `today_start = now.replace(h=0,m=0,s=0,µs=0)` | NO (hardcoded UTC) |
| Monthly | Calendar month | `timestamp >= month_start` where `month_start = now.replace(d=1,h=0,m=0,s=0,µs=0)` | NO (hardcoded UTC) |

**All boundaries use `datetime.utcnow()`** — not timezone-aware!

## Performance Scaling

| Records | Scan Time | Notes |
|---------|-----------|-------|
| 50 | <1ms | Current live data |
| 500 | <10ms | Acceptable |
| 5,000 | ~100ms | Still usable |
| 50,000 | 1-2s | Becoming noticeable |

## Report Formats (5 Available)

### 1. Cost Summary
```python
costs_parser.get_cost_summary(session_id=None)
# Returns: {"session_cost_usd", "daily_cost_usd", "monthly_cost_usd", "total_tokens", "request_count", "by_model": {...}}
```

### 2. Budget Status
```python
budget_manager.check_budget(period="daily"|"monthly")
# Returns: {"status": ALLOWED|WARNING|EXCEEDED|DISABLED, "current_usd", "limit_usd", "percent_used", "message"}
```

### 3. Budget Summary
```python
budget_manager.get_budget_summary()
# Returns: {"enabled", "daily": {...}, "monthly": {...}, "session": {...}, "limits": {...}}
```

### 4. Recent Costs
```python
costs_parser.get_recent_costs(hours=24, limit=100)
# Returns: [full cost records, most recent first]
```

### 5. Token History
```python
costs_parser.get_token_history(hours=24)
# Returns: [{"timestamp", "input_tokens", "output_tokens", "total_tokens", "cost_usd"}, ...]
```

## Configuration

**File**: `~/.zeroclaw/config.toml`

```toml
[cost]
enabled = true                 # Enable/disable cost tracking
daily_limit_usd = 10.0        # Daily budget
monthly_limit_usd = 100.0     # Monthly budget
warn_at_percent = 80          # Warning threshold
allow_override = false        # Can bypass when exceeded
```

## Actual Data (50 Records, Jan 21 - Feb 21, 2026)

### By Session
```
Session b9b607f9... : 14 requests, $0.3188, 56,569 tokens
Session ec1a8033... : 27 requests, $0.9548, 162,857 tokens
Session ae6b5bf6... :  9 requests, $0.5254, 51,934 tokens
```

### By Model
```
anthropic/claude-sonnet-4   : 58 req, $0.7068 (39%)
anthropic/claude-3.5-sonnet : 11 req, $0.6342 (35%)
openai/gpt-4o              :  8 req, $0.2918 (16%)
openai/gpt-4o-mini         :  2 req, $0.0065 (<1%)
```

### Cost Range
- Min: $0.000758 per request (GPT-4o-mini)
- Max: $0.047860 per request (GPT-4o)
- Average: $0.0227 per request

## Code Locations

| Purpose | File | Key Function |
|---------|------|--------------|
| Aggregation engine | `lib/costs_parser.py` (250 lines) | `CostsParser.get_cost_summary()` |
| Budget enforcement | `lib/budget_manager.py` (242 lines) | `BudgetManager.check_budget()` |
| UI component | `components/dashboard/cost_tracking.py` (215 lines) | `render()` |
| Config mgmt | `lib/budget_manager.py` | `BudgetManager._load_config()` |
| Sample generation | `scripts/generate_sample_costs.py` (133 lines) | `generate_sample_costs()` |

## Critical Gaps

| Gap | Impact | Fix Effort |
|-----|--------|-----------|
| No timezone support | Wrong daily boundaries in non-UTC zones | MEDIUM |
| No retention policy | Data loss risk, no audit trail | MEDIUM |
| No trend detection | Cannot forecast or identify anomalies | HIGH |
| No period comparison | Cannot compare Feb vs Jan | MEDIUM |
| No multi-tenant tracking | Single file for all users | HIGH |
| No data export | Cannot integrate with accounting | LOW |

## Top 3 Recommendations (Priority Order)

1. **Implement timezone-aware aggregation** (1-2 weeks)
   - Add `timezone` parameter to `get_cost_summary()`
   - Use local midnight instead of UTC

2. **Add retention policy** (1-2 weeks)
   - Monthly file rotation: `costs.jsonl` → `costs-2026-02.jsonl`
   - Archive old months
   - Implement on startup

3. **Add basic trend widget** (1 week)
   - 7-day cost sparkline
   - % change vs. last week
   - Show on dashboard

## Known Issues

1. **UTC-only aggregation**: All boundaries hardcoded to UTC
2. **No auto-session-boundaries**: Sessions manually managed
3. **No distributed tracking**: Single file only (no multi-machine)
4. **No backup mechanism**: Manual rotation required
5. **No precision specification**: Float arithmetic risks accumulation errors

## Future Enhancements (Prioritized)

### Phase 1 (Immediate)
- Timezone awareness
- Retention policy + file rotation
- Cost trend sparklines

### Phase 2 (1 month)
- Period comparison (Feb vs Jan)
- Daily breakdown by model (stacked bar)
- Custom date range filtering

### Phase 3 (2-3 months)
- Forecasting / budget projection
- Webhook alerting
- CSV/JSON export
- SQL query interface

---

**Full Report**: `/Users/jakeprivate/zeroclaw/AGENT_05_COSTS_REPORT.md`
**Investigation Date**: 2026-02-21
**Records Analyzed**: 50 (Jan 21 - Feb 21, 2026)
**Total Cost in Dataset**: $1.80 USD
