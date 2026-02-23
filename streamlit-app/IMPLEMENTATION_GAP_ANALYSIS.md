# Implementation Gap Analysis

Current state of the ZeroClaw Streamlit UI as of 2026-02-23.

## What Works Now (Real / Wired)

### Chat Page (`pages/chat.py`)
- Message input with model selector (correct model list: claude-sonnet-4-6, claude-opus-4-6, etc.)
- Message history display with timestamps and metadata
- Real CLI execution via `ZeroClawCLIExecutor.execute_oneshot()` -- runs `zeroclaw agent -m <message> --model <model>`
- Conversation save/load to `~/.zeroclaw/conversations/` (JSON files)
- Conversation export (text and JSON formats)
- Alternative live chat component (`components/chat/live_chat.py`) with streaming support

### Sidebar (`components/sidebar.py`)
- Real gateway health check (HTTP GET to `{gateway_url}/health`)
- Real binary detection (checks `~/zeroclaw/target/release/zeroclaw` and `$PATH`)
- Page navigation (Dashboard, Chat, Analytics, Reports, Analyze, Settings)

### Dashboard - Cost Tracking (`components/dashboard/cost_tracking.py`)
- Reads real cost data from `~/.zeroclaw/state/costs.jsonl` via `costs_parser`
- Session/daily/monthly cost metrics with budget percentage
- Budget alerts (warning/exceeded thresholds from config)
- Cost breakdown by model (donut chart)

### Dashboard - Token Usage (`components/dashboard/token_usage.py`)
- Reads real token data from `costs.jsonl`
- Total tokens, average per request, request count
- 24-hour token usage timeline (stacked area chart)
- Input vs output token breakdown by model

### Dashboard - Real-Time Metrics (`components/dashboard/real_time_metrics.py`)
- Configured agent count from `config.toml`
- Session requests, total tokens, session cost from `costs.jsonl`

### Dashboard - Agent Config Status (`components/dashboard/agent_config_status.py`)
- Reads agent definitions from `~/.zeroclaw/config.toml`
- Shows default agent, configured agents, provider distribution, autonomy level

### Dashboard - Agent Status Monitor (`components/dashboard/agent_status_monitor.py`)
- Reads agent list from `config.toml`
- Displays provider, model, temperature per agent

### Analytics - Delegations Tab (`pages/analytics.py`, tab 5)
- Full delegation tracking from `~/.zeroclaw/state/delegation.jsonl`
- Cross-run charts: cost by run, tokens by model, depth distribution, success rate
- Agent/model/provider/depth stats tables
- Error, slow, cost breakdown, recent, active delegation tables
- Time-bucketed breakdowns (daily, hourly, monthly, quarterly, weekday)
- Duration/token/cost bucket histograms
- Agent leaderboard, run comparison (diff)
- Export buttons (CSV + JSONL)
- Log health panel with prune action
- Live mode (auto-refresh at configurable intervals)
- Timeline waterfall (Gantt chart)
- Delegation tree visualization

### Analytics - Overview/Performance/Errors/Usage Charts
- Request volume chart reads real `DelegationStart` events from `delegation.jsonl`
- Request distribution, response time, performance metrics, error rate, error types, user activity, feature usage charts all read from `delegation.jsonl`

### Settings Page (`pages/settings.py`)
- Gateway URL and API token configuration (persisted to `config.json`)
- Real connection test (HTTP request to gateway)
- Theme selector (Matrix Green active, others marked coming soon)
- Font size, debug mode, auto-refresh preferences
- Debug view of full session state

### Reports Page (`pages/reports.py`)
- Report listing via gateway API (`/api/reports`)
- Report viewer dialog with table of contents
- PDF export capability

### Analyze Page (`pages/analyze.py`)
- Analysis configuration form (data source, type, output format)
- Activity stream logging for submitted analyses

### Shared Infrastructure
- Session state management (`lib/session_state.py`) -- centralized defaults
- Conversation manager (`lib/conversation_manager.py`) -- filesystem persistence
- Response streamer (`lib/response_streamer.py`) -- CLI output parsing
- Tool approval dialog (`components/chat/tool_approval_dialog.py`) -- security review UI
- Matrix Green CSS theme applied globally

## What Shows Honest Empty State

These components gracefully handle missing data without faking it:

- **Real-Time Metrics**: shows "--" and "No data yet" when `costs.jsonl` is absent
- **Cost Tracking**: shows "No cost data found" message with file path hint
- **Token Usage**: shows "No token usage data found" when no cost data exists
- **Agent Status Monitor**: shows "No agents configured" when `config.toml` has none
- **Agent Config Status**: shows "No additional agents configured" with config hint
- **Activity Stream**: shows "No activity yet" with guidance
- **Delegation Tree**: shows empty state when `delegation.jsonl` is absent
- **All analytics charts** (request volume, distribution, etc.): show "No delegation data available" with guidance to run ZeroClaw
- **All delegation tables** (errors, slow, recent, active, etc.): show informational empty states
- **Reports listing**: shows connection error when gateway is offline

## What Still Has Hardcoded Values

### Analytics Page Summary Metrics (`pages/analytics.py` lines 54-85)
The four summary metrics at the top of the Analytics page are hardcoded:
- "Total Requests: 12,543"
- "Avg Response: 234ms"
- "Error Rate: 2.1%"
- "Active Users: 1,234"

These do not read from any data source. The individual chart tabs below them do use real data.

## What Needs ZeroClaw Running

### Chat (requires binary)
- **Binary path**: `~/zeroclaw/target/release/zeroclaw`
- **Fallback**: also checks `$PATH` for `zeroclaw`
- **What happens without it**: chat shows "ZeroClaw binary not found. Build it with: cargo build --release"

### Cost and Token Tracking (requires ZeroClaw to have run)
- **State file**: `~/.zeroclaw/state/costs.jsonl`
- **Config requirement**: `[cost] enabled = true` in `~/.zeroclaw/config.toml`
- **What happens without it**: dashboard cost/token components show empty state messages

### Delegation Analytics (requires ZeroClaw to have run with delegations)
- **State file**: `~/.zeroclaw/state/delegation.jsonl`
- **What happens without it**: all delegation charts/tables show "No delegation data available"
- **How to populate**: run ZeroClaw with workflows that use the `delegate` tool

### Gateway Features (requires `zeroclaw gateway` running)
- **Default URL**: `http://localhost:3000`
- **Configurable in**: Settings page or session state
- **What depends on it**:
  - Sidebar connection status indicator
  - Reports page (listing, viewing, exporting)
  - Quick Actions panel (restart gateway, start/stop agents, etc.)
  - Settings page "Test Connection" button
- **What happens without it**: sidebar shows "Gateway offline", reports show connection error

### Agent Configuration (requires config file)
- **Config file**: `~/.zeroclaw/config.toml`
- **What depends on it**: agent count, agent cards, provider distribution, autonomy level
- **What happens without it**: shows 0 agents with "No agents configured" message

## How to Start

```bash
# 1. Build the ZeroClaw binary
cd ~/zeroclaw
cargo build --release

# 2. Initialize configuration (if first time)
./target/release/zeroclaw onboarding

# 3. (Optional) Start the gateway for reports and remote features
./target/release/zeroclaw gateway &

# 4. Run at least one agent command to populate cost/token data
./target/release/zeroclaw agent -m "hello" --model claude-sonnet-4-6

# 5. Start the Streamlit app
cd ~/zeroclaw/streamlit-app
pip install -r requirements.txt  # first time only
streamlit run app.py
```

The app opens at `http://localhost:8501`. Pages will progressively show real data as ZeroClaw generates state files.
