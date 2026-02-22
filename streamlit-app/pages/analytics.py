"""Analytics Page.

This page provides comprehensive analytics and metrics visualization with interactive
charts organized into tabs for different analytical perspectives (Overview, Performance,
Errors, Usage). Uses Matrix Green theme throughout.
"""

import time
from datetime import datetime

import streamlit as st
from components import analytics
from components.analytics import delegation_charts
from components.dashboard import delegation_tree
from lib.session_state import get_state, set_state


def render() -> None:
    """Render the Analytics page with all integrated chart components.

    Page structure:
    - Header with title and description
    - Time range selector and export button
    - Summary metrics cards (4 key metrics)
    - Tabbed chart views:
      - Overview: Request volume & distribution
      - Performance: Response time & performance metrics
      - Errors: Error rate & error types breakdown
      - Usage: User activity & feature usage
    """
    # Page header
    st.title("Analytics")
    st.caption("Monitor performance metrics and insights over time")

    # Time range selector and controls
    col1, col2 = st.columns([3, 1])
    with col1:
        time_range = st.selectbox(
            "Time Range",
            ["24h", "7d", "30d", "90d", "1y"],
            index=1,  # Default to 7d
            key="analytics_time_range"
        )
        # Store in session state for chart components to access
        set_state('time_range', time_range)

    with col2:
        # Placeholder for export functionality
        st.button("Export", disabled=True, help="Export functionality coming soon")

    # Summary metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Requests",
            value="12,543",
            delta="8.2%",
            help="Total number of requests in selected time range"
        )

    with col2:
        st.metric(
            label="Avg Response",
            value="234ms",
            delta="-12ms",
            help="Average response time across all requests"
        )

    with col3:
        st.metric(
            label="Error Rate",
            value="2.1%",
            delta="-0.3%",
            delta_color="inverse",
            help="Percentage of failed requests"
        )

    with col4:
        st.metric(
            label="Active Users",
            value="1,234",
            delta="45",
            help="Number of active users in selected time range"
        )

    # Divider between metrics and charts
    st.divider()

    # Tabbed chart views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview",
        "Performance",
        "Errors",
        "Usage",
        "Delegations"
    ])

    # Overview Tab: Request patterns and distribution
    with tab1:
        st.markdown("### Request Overview")
        st.caption("Monitor request volume trends and distribution across categories")

        col1, col2 = st.columns(2)

        with col1:
            analytics.request_volume_chart()

        with col2:
            analytics.request_distribution_chart()

    # Performance Tab: Response time and latency metrics
    with tab2:
        st.markdown("### Performance Metrics")
        st.caption("Analyze response times and latency percentiles across services")

        col1, col2 = st.columns(2)

        with col1:
            analytics.response_time_chart()

        with col2:
            analytics.performance_metrics_chart()

    # Errors Tab: Error rates and type breakdown
    with tab3:
        st.markdown("### Error Analysis")
        st.caption("Track error rates over time and analyze error type distribution")

        col1, col2 = st.columns(2)

        with col1:
            analytics.error_rate_chart()

        with col2:
            analytics.error_types_chart()

    # Usage Tab: User activity and feature adoption
    with tab4:
        st.markdown("### Usage Analytics")
        st.caption("Monitor user activity trends and feature usage patterns")

        col1, col2 = st.columns(2)

        with col1:
            analytics.user_activity_chart()

        with col2:
            analytics.feature_usage_chart()

    # Delegations Tab: Agent delegation tree visualization + cross-run analytics
    with tab5:
        st.markdown("### Agent Delegations")
        st.caption("Visualize nested agent delegation hierarchies and cross-run cost/token analytics")

        # ── Live-mode controls ─────────────────────────────────────────────
        live_col1, live_col2, live_col3 = st.columns([2, 2, 3])
        with live_col1:
            live_mode = st.checkbox(
                "Live mode",
                value=False,
                key="delegation_live_mode",
                help="Automatically re-read the JSONL log and refresh all charts "
                     "at the selected interval. Useful when ZeroClaw is actively running.",
            )
        with live_col2:
            if live_mode:
                refresh_interval = st.selectbox(
                    "Refresh every",
                    options=[3, 5, 10, 30],
                    index=1,  # default 5 s
                    format_func=lambda x: f"{x}s",
                    key="delegation_refresh_interval",
                )
            else:
                refresh_interval = 5
                if st.button("↻ Refresh", key="delegation_refresh_btn",
                             help="Re-read delegation log now"):
                    st.rerun()
        with live_col3:
            last_refresh = st.session_state.get("delegation_last_refresh")
            if live_mode and last_refresh:
                st.caption(f"Last refreshed: {last_refresh}")
            elif not live_mode:
                st.caption("Enable live mode to auto-refresh while ZeroClaw runs")

        st.divider()

        # Log health panel (collapsible)
        delegation_charts.render_log_health()

        # Shared run selector — controls summary, timeline, and tree simultaneously
        selected_run_id = delegation_charts.render_run_selector()

        # Delegation summary metrics (scoped to selected run)
        delegation_tree.render_delegation_summary(run_id=selected_run_id)

        st.divider()

        # Cross-run analytics charts (always show full history, unaffected by selector)
        st.markdown("#### Cross-Run Analytics")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            delegation_charts.render_cost_by_run()
        with chart_col2:
            delegation_charts.render_tokens_by_model()

        chart_col3, chart_col4 = st.columns(2)
        with chart_col3:
            delegation_charts.render_depth_distribution()
        with chart_col4:
            delegation_charts.render_success_rate_by_depth()

        # Agent leaderboard (global, all runs, mirrors zeroclaw delegations top)
        delegation_charts.render_agent_leaderboard()

        # Run Comparison (mirrors zeroclaw delegations diff)
        delegation_charts.render_run_diff()

        # Agent breakdown charts (scoped to selected run when set)
        st.markdown("#### Agent Breakdown")
        agent_col1, agent_col2 = st.columns(2)
        with agent_col1:
            delegation_charts.render_tokens_by_agent(run_id=selected_run_id)
        with agent_col2:
            delegation_charts.render_cost_by_agent(run_id=selected_run_id)

        # Per-agent stats table (scoped to selected run when set)
        delegation_charts.render_agent_stats_table(run_id=selected_run_id)

        # Per-model stats table (scoped to selected run when set)
        delegation_charts.render_model_stats_table(run_id=selected_run_id)

        # Per-provider stats table (scoped to selected run when set)
        delegation_charts.render_providers_stats_table(run_id=selected_run_id)

        # Per-depth stats table (scoped to selected run when set)
        delegation_charts.render_depth_stats_table(run_id=selected_run_id)

        # Errors table — failed delegations only (scoped to selected run when set)
        delegation_charts.render_errors_table(run_id=selected_run_id)

        # Slow table — N slowest delegations by duration (scoped to selected run when set)
        delegation_charts.render_slow_table(run_id=selected_run_id)

        # Cost breakdown table — per-run cost sorted descending (scoped to selected run when set)
        delegation_charts.render_cost_breakdown_table(run_id=selected_run_id)

        # Recent table — N most recently completed delegations, newest first
        delegation_charts.render_recent_table(run_id=selected_run_id)

        # Active table — currently in-flight delegations (scoped to selected run when set)
        delegation_charts.render_active_table(run_id=selected_run_id)

        # Agent history table — per-agent delegation history (scoped to selected run when set)
        delegation_charts.render_agent_history_table(run_id=selected_run_id)

        # Model history table — per-model delegation history (scoped to selected run when set)
        delegation_charts.render_model_history_table(run_id=selected_run_id)

        # Provider history table — per-provider delegation history (scoped to selected run when set)
        delegation_charts.render_provider_history_table(run_id=selected_run_id)

        # Run report table — full chronological delegation report for the selected run
        delegation_charts.render_run_report_table(run_id=selected_run_id)

        # Depth-view table — per-depth-level delegation listing (scoped to selected run when set)
        delegation_charts.render_depth_view_table(run_id=selected_run_id)

        # Daily breakdown table — per-calendar-day aggregation (scoped to selected run when set)
        delegation_charts.render_daily_breakdown_table(run_id=selected_run_id)

        # Hourly breakdown table — per-UTC-hour aggregation (scoped to selected run when set)
        delegation_charts.render_hourly_breakdown_table(run_id=selected_run_id)

        # Monthly breakdown table — per-calendar-month aggregation (scoped to selected run when set)
        delegation_charts.render_monthly_breakdown_table(run_id=selected_run_id)

        # Quarterly breakdown table — per-calendar-quarter aggregation (scoped to selected run when set)
        delegation_charts.render_quarterly_breakdown_table(run_id=selected_run_id)

        # Agent × model cross-product breakdown table (scoped to selected run when set)
        delegation_charts.render_agent_model_table(run_id=selected_run_id)

        # Provider × model cross-product breakdown table (scoped to selected run when set)
        delegation_charts.render_provider_model_table(run_id=selected_run_id)

        # Agent × provider cross-product breakdown table (scoped to selected run when set)
        delegation_charts.render_agent_provider_table(run_id=selected_run_id)

        # Duration bucket histogram table (scoped to selected run when set)
        delegation_charts.render_duration_bucket_table(run_id=selected_run_id)

        # Token bucket histogram table (scoped to selected run when set)
        delegation_charts.render_token_bucket_table(run_id=selected_run_id)

        # Cost bucket histogram table (scoped to selected run when set)
        delegation_charts.render_cost_bucket_table(run_id=selected_run_id)

        # Weekday breakdown table (scoped to selected run when set)
        delegation_charts.render_weekday_table(run_id=selected_run_id)

        # ISO week breakdown table (scoped to selected run when set)
        delegation_charts.render_weekly_table(run_id=selected_run_id)

        # Depth bucket histogram table (scoped to selected run when set)
        delegation_charts.render_depth_bucket_table(run_id=selected_run_id)

        # Model-tier breakdown table (scoped to selected run when set)
        delegation_charts.render_model_tier_table(run_id=selected_run_id)

        # Provider-tier breakdown table (scoped to selected run when set)
        delegation_charts.render_provider_tier_table(run_id=selected_run_id)

        # Time-of-day breakdown table (scoped to selected run when set)
        delegation_charts.render_time_of_day_table(run_id=selected_run_id)

        # Day-of-month breakdown table (scoped to selected run when set)
        delegation_charts.render_day_of_month_table(run_id=selected_run_id)

        # Token efficiency breakdown table (scoped to selected run when set)
        delegation_charts.render_token_efficiency_table(run_id=selected_run_id)

        # Success breakdown table (scoped to selected run when set)
        delegation_charts.render_success_breakdown_table(run_id=selected_run_id)

        # Agent cost rank table (scoped to selected run when set)
        delegation_charts.render_agent_cost_rank_table(run_id=selected_run_id)

        # Model cost rank table (scoped to selected run when set)
        delegation_charts.render_model_cost_rank_table(run_id=selected_run_id)

        # Provider cost rank table (scoped to selected run when set)
        delegation_charts.render_provider_cost_rank_table(run_id=selected_run_id)

        # Run cost rank table (scoped to selected run when set)
        delegation_charts.render_run_cost_rank_table(run_id=selected_run_id)

        # Agent success rank table (scoped to selected run when set)
        delegation_charts.render_agent_success_rank_table(run_id=selected_run_id)

        # Model success rank table (scoped to selected run when set)
        delegation_charts.render_model_success_rank_table(run_id=selected_run_id)

        # Provider success rank table (scoped to selected run when set)
        delegation_charts.render_provider_success_rank_table(run_id=selected_run_id)

        # Agent token rank table (scoped to selected run when set)
        delegation_charts.render_agent_token_rank_table(run_id=selected_run_id)

        # Model token rank table (scoped to selected run when set)
        delegation_charts.render_model_token_rank_table(run_id=selected_run_id)

        # Provider token rank table (scoped to selected run when set)
        delegation_charts.render_provider_token_rank_table(run_id=selected_run_id)

        # Agent duration rank table (scoped to selected run when set)
        delegation_charts.render_agent_duration_rank_table(run_id=selected_run_id)

        # Export buttons (CSV + JSONL, scoped to selected run when set)
        delegation_charts.render_export_buttons(run_id=selected_run_id)

        # Timeline waterfall (scoped to selected run)
        delegation_charts.render_timeline(run_id=selected_run_id)

        st.divider()

        # Delegation tree (scoped to selected run; suppress internal selector
        # when a specific run is already chosen from the shared selector above)
        delegation_tree.render_delegation_tree(
            run_id=selected_run_id,
            show_run_selector=(selected_run_id is None),
            use_mock_data=False,
        )

        # Live mode: record render time, sleep, then rerun
        if live_mode:
            st.session_state["delegation_last_refresh"] = (
                datetime.now().strftime("%H:%M:%S")
            )
            st.caption(
                f"Live mode active — refreshing in {refresh_interval}s "
                f"(disable to stop)"
            )
            time.sleep(refresh_interval)
            st.rerun()

        # Instructions for delegation tracking
        with st.expander("ℹ️ About Delegation Tracking"):
            st.markdown("""
            The delegation tracking system records nested agent delegations end-to-end,
            from the Rust backend through to this UI.

            **How it works:**

            1. **Backend** — `DelegationEventObserver` generates a UUID `run_id` at startup
               and writes `DelegationStart` / `DelegationEnd` events to JSONL
            2. **Token capture** — `CapturingObserver` intercepts `AgentEnd` events from
               each sub-agent and propagates `tokens_used` / `cost_usd` into `DelegationEnd`
            3. **Storage** — append-only at `~/.zeroclaw/state/delegation.jsonl`
            4. **UI** — this page reads the JSONL, filters by run, and builds the tree

            **What you see:**

            - **Cross-run charts** — cost per run, token breakdown by model, depth
              distribution, and success/failure rates across all historical runs
            - **Agent Breakdown** — tokens and cost per agent name, scoped to the
              selected run when a specific run is chosen in the shared run selector;
              shows aggregate across all runs when "All runs" is selected
            - **Agent Stats table** — sortable dataframe with one row per agent:
              delegation count, ended count, success %, average duration, total tokens,
              and total cost; mirrors `zeroclaw delegations stats`; scoped by the
              shared run selector
            - **Model Stats table** — sortable dataframe with one row per model:
              delegation count, ended count, success %, total tokens, and total cost;
              mirrors `zeroclaw delegations models`; scoped by the shared run selector;
              useful for comparing token/cost footprint across provider models
            - **Provider Stats table** — sortable dataframe with one row per provider
              (e.g. "anthropic", "openai"): delegation count, ended count, success %,
              total tokens, and total cost; mirrors `zeroclaw delegations providers`;
              scoped by the shared run selector; useful for seeing cost distribution
              across AI providers at a glance
            - **Depth Stats table** — sortable dataframe with one row per nesting level
              (depth 0 = root agent, depth 1 = direct sub-agents, etc.): delegation
              count, ended count, success %, total tokens, and total cost; sorted
              ascending by depth; mirrors `zeroclaw delegations depth`; scoped by the
              shared run selector; useful for understanding how deeply workflows nest
              and where token spend concentrates
            - **Delegation Errors table** — rows for every failed delegation
              (success=False), sorted oldest-first; columns show run prefix, agent
              name, depth, duration, and full error message; mirrors
              `zeroclaw delegations errors`; scoped by the shared run selector;
              shows a mock example when no failures exist in the selected scope
            - **Slowest Delegations table** — rows for the N slowest completed
              delegations, sorted by duration descending; a number-input controls
              how many rows to show (default: 10, matches CLI `--limit`); columns
              show run prefix, agent, depth, duration in ms, tokens, and cost;
              mirrors `zeroclaw delegations slow`; scoped by the shared run selector
            - **Cost Breakdown table** — one row per stored run sorted by total
              cost descending (most expensive first); columns show run prefix,
              start time, delegation count, tokens, total cost, and average cost
              per completed delegation; mirrors `zeroclaw delegations cost`;
              scoped by the shared run selector
            - **Most Recent Delegations table** — rows for the N most recently
              completed delegations sorted by finish timestamp descending (newest
              first); a number-input controls how many rows to show (default: 10,
              matches CLI `--limit`); columns show run prefix, agent, depth,
              duration, tokens, cost, and finish timestamp; mirrors
              `zeroclaw delegations recent`; scoped by the shared run selector
            - **Active (In-Flight) Delegations table** — rows for delegations
              that have a `DelegationStart` event but no matching `DelegationEnd`;
              FIFO matching per (run_id, agent_name, depth) key handles concurrent
              same-agent delegations correctly; sorted oldest-start first; columns
              show run prefix, agent, depth, start timestamp, and elapsed time;
              mirrors `zeroclaw delegations active`; scoped by the shared run
              selector; shows a mock example when no real log data is available
            - **Agent History table** — text input for an agent name (exact,
              case-sensitive match); shows every completed delegation for that
              agent sorted newest first; columns show run prefix, depth, duration,
              tokens, cost, ok flag, and finish timestamp; a caption line below
              summarises total occurrences, success count, cumulative tokens, and
              cumulative cost; mirrors `zeroclaw delegations agent <name>`;
              scoped by the shared run selector; shows a mock example when no
              real log data is available; hides the table and returns early when
              the agent name field is left blank
            - **Model History table** — text input for a model name (exact,
              case-sensitive match); shows every completed delegation for that
              model sorted newest first; includes an Agent column so different
              agents using the same model are distinguishable; columns show run
              prefix, agent, depth, duration, tokens, cost, ok flag, and finish
              timestamp; a caption line below summarises total occurrences,
              success count, cumulative tokens, and cumulative cost; mirrors
              `zeroclaw delegations model <name>`; scoped by the shared run
              selector; shows a mock example when no real log data is available;
              hides the table and returns early when the model name field is left
              blank
            - **Provider History table** — text input for a provider name (exact,
              case-sensitive match); shows every completed delegation for that
              provider sorted newest first; includes Agent and Model columns so
              different agents and models on the same provider are distinguishable;
              columns show run prefix, agent, model, depth, duration, tokens, cost,
              ok flag, and finish timestamp; a caption line below summarises total
              occurrences, success count, cumulative tokens, and cumulative cost;
              mirrors `zeroclaw delegations provider <name>`; scoped by the shared
              run selector; shows a mock example when no real log data is available;
              hides the table and returns early when the provider name field is left
              blank
            - **Run Report table** — shows all completed delegations for the
              currently selected run in chronological order (oldest first, no row
              limit); requires a run to be chosen in the shared run selector (shows
              a prompt when no run is selected); columns show agent, depth, duration,
              tokens, cost, ok flag, and finish timestamp; a caption line below
              summarises total completions, success count, cumulative tokens, and
              cumulative cost; mirrors `zeroclaw delegations run <id>`; shows a mock
              example when no real log data is available for the selected run
            - **Depth-View table** — numeric stepper selects a nesting depth (0 =
              root-level, 1 = sub-delegations, etc.); shows every completed
              delegation at that depth sorted newest first; columns show run prefix,
              agent, duration, tokens, cost, ok flag, and finish timestamp; a caption
              line below summarises total occurrences, success count, cumulative
              tokens, and cumulative cost; mirrors `zeroclaw delegations depth-view
              <level>`; scoped by the shared run selector; shows a mock example when
              no real log data is available
            - **Daily Breakdown table** — groups all completed delegations by UTC
              calendar date (oldest day first); columns show date, delegation count,
              success percentage, cumulative tokens, and cumulative cost; a caption
              line below summarises total days, total delegations, successes, and
              cumulative cost; mirrors `zeroclaw delegations daily`; scoped by the
              shared run selector; shows a mock example when no real log data is
              available
            - **Hourly Breakdown table** — groups all completed delegations by UTC
              hour-of-day (00–23, lowest first); columns show hour bucket, delegation
              count, success percentage, cumulative tokens, and cumulative cost; events
              from different dates with the same hour merge into one bucket to reveal
              peak-activity windows; a caption line below summarises active hours,
              total delegations, successes, and cumulative cost; mirrors
              `zeroclaw delegations hourly`; scoped by the shared run selector; shows
              a mock example when no real log data is available
            - **Monthly Breakdown table** — groups all completed delegations by UTC
              calendar month (YYYY-MM, oldest first); columns show month, delegation
              count, success percentage, cumulative tokens, and cumulative cost; a
              caption line below summarises total months, total delegations,
              successes, and cumulative cost; mirrors `zeroclaw delegations monthly`;
              scoped by the shared run selector; shows a mock example when no real
              log data is available
            - **Quarterly Breakdown table** — groups all completed delegations by UTC
              calendar quarter (YYYY-QN, oldest first); quarter boundaries are
              Jan–Mar = Q1, Apr–Jun = Q2, Jul–Sep = Q3, Oct–Dec = Q4; columns show
              quarter, delegation count, success percentage, cumulative tokens, and
              cumulative cost; a caption line below summarises total quarters, total
              delegations, successes, and cumulative cost; mirrors
              `zeroclaw delegations quarterly`; scoped by the shared run selector;
              shows a mock example when no real log data is available
            - **Agent × Model Breakdown table** — cross-product of (agent_name ×
              model) pairs ranked by total tokens consumed (descending); columns show
              rank, agent name, model, delegation count, cumulative tokens, and
              cumulative cost; a caption line below summarises total distinct
              combinations, total delegations, and cumulative cost; mirrors
              `zeroclaw delegations agent-model`; scoped by the shared run selector;
              shows a mock example when no real log data is available
            - **Provider × Model Breakdown table** — cross-product of (provider ×
              model) pairs ranked by total tokens consumed (descending); columns show
              rank, provider name, model, delegation count, cumulative tokens, and
              cumulative cost; a caption line below summarises total distinct
              combinations, total delegations, and cumulative cost; mirrors
              `zeroclaw delegations provider-model`; scoped by the shared run selector;
              shows a mock example when no real log data is available
            - **Agent × Provider Breakdown table** — cross-product of (agent_name ×
              provider) pairs ranked by total tokens consumed (descending); columns
              show rank, agent name, provider, delegation count, cumulative tokens, and
              cumulative cost; a caption line below summarises total distinct
              combinations, total delegations, and cumulative cost; mirrors
              `zeroclaw delegations agent-provider`; scoped by the shared run selector;
              shows a mock example when no real log data is available
            - **Duration Bucket table** — groups completed delegations into five
              fixed-width latency buckets (&lt;500ms, 500ms–2s, 2s–10s, 10s–60s, &gt;60s);
              columns show bucket label, count, success percentage, cumulative tokens,
              and cumulative cost; buckets are shown in fastest-to-slowest order and
              empty buckets are omitted; a caption line below summarises populated
              bucket count, total delegations, total successes, and cumulative cost;
              mirrors `zeroclaw delegations duration-bucket`; scoped by the shared run
              selector; shows a mock example when no real log data is available
            - **Token Bucket table** — groups completed delegations into five
              fixed-width token-usage buckets (0–99, 100–999, 1k–9.9k, 10k–99.9k,
              100k+); columns show bucket label, count, success percentage, cumulative
              tokens, and cumulative cost; buckets are shown in smallest-to-largest
              order and empty buckets are omitted; a caption line below summarises
              populated bucket count, total delegations, total successes, and
              cumulative cost; mirrors `zeroclaw delegations token-bucket`; scoped
              by the shared run selector; shows a mock example when no real log data
              is available
            - **Cost Bucket table** — groups completed delegations into five
              fixed-width cost tiers (&lt;$0.001, $0.001–$0.01, $0.01–$0.10,
              $0.10–$1.00, ≥$1.00); columns show bucket label, count, success
              percentage, cumulative tokens, and cumulative cost; buckets are shown
              in cheapest-to-most-expensive order and empty buckets are omitted; a
              caption line below summarises populated bucket count, total delegations,
              total successes, and cumulative cost; mirrors
              `zeroclaw delegations cost-bucket`; scoped by the shared run selector;
              shows a mock example when no real log data is available
            - **Agent Leaderboard** — horizontal bar chart ranking all agents by
              cumulative tokens or cost across every stored run; rank-by and top-N
              controls mirror `zeroclaw delegations top`; falls back to a mock
              example when no real delegation data is available
            - **Run Comparison** — side-by-side grouped bar charts (tokens and cost
              per agent) comparing two independently selected runs; four aggregate
              Δ metrics show the net change in total tokens and cost between runs;
              mirrors `zeroclaw delegations diff`; falls back to a mock example
              when fewer than two real runs are stored
            - **Export buttons** — Download CSV or JSONL of real delegation data;
              CSV columns match `zeroclaw delegations export --format csv`; JSONL
              contains raw event lines; both are scoped to the selected run when set;
              buttons are disabled when no real log data is available
            - **Log Health** — collapsible panel showing file size, run count,
              time range, and cumulative token/cost totals across all stored runs;
              includes a **Prune** action (keep-N number input + button) that
              atomically removes old runs from the JSONL log, mirroring
              `zeroclaw delegations prune --keep N`; the panel refreshes
              automatically after pruning
            - **Live mode** — auto-refresh toggle (3 / 5 / 10 / 30s intervals)
              that re-reads the JSONL log and rerenders all charts; use while
              ZeroClaw is actively running to watch delegations appear in real time
            - **Timeline waterfall** — Gantt-style chart showing each delegation
              as a horizontal bar positioned by actual start/end timestamps;
              makes concurrency and relative duration immediately visible
            - **Shared Run Selector** — single dropdown above the summary that
              synchronises the summary metrics, timeline waterfall, and delegation
              tree to one process invocation; cross-run charts are unaffected
            - **Delegation Tree** — hierarchical agent → sub-agent view with status,
              duration, tokens, and cost per node
            - **Prometheus metrics** — `zeroclaw_delegations_total`,
              `zeroclaw_delegation_duration_seconds`,
              `zeroclaw_delegation_tokens_total`,
              `zeroclaw_delegation_cost_usd_total`

            **Event format (JSONL):**
            ```json
            {"event_type":"DelegationStart","run_id":"f47ac10b-...","agent_name":"research","provider":"anthropic","model":"claude-sonnet-4","depth":1,"agentic":true,"timestamp":"2026-02-22T10:30:45Z"}
            {"event_type":"DelegationEnd","run_id":"f47ac10b-...","agent_name":"research","provider":"anthropic","model":"claude-sonnet-4","depth":1,"duration_ms":4512,"success":true,"error_message":null,"tokens_used":1234,"cost_usd":0.0037,"timestamp":"2026-02-22T10:30:50Z"}
            ```

            **If no delegation data appears:** run ZeroClaw with a workflow that uses
            the `delegate` tool to trigger sub-agent delegations.
            """)


# Entry point for Streamlit multi-page app
if __name__ == "__main__":
    render()
