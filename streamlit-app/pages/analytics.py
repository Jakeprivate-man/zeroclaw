"""Analytics Page.

This page provides comprehensive analytics and metrics visualization with interactive
charts organized into tabs for different analytical perspectives (Overview, Performance,
Errors, Usage). Uses Matrix Green theme throughout.
"""

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

        # Delegation summary metrics
        delegation_tree.render_delegation_summary()

        st.divider()

        # Cross-run analytics charts
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

        st.divider()

        # Delegation tree visualization (real data from JSONL)
        delegation_tree.render_delegation_tree(use_mock_data=False)

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
            - **Run Selector** — filter the tree to a single process invocation
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
