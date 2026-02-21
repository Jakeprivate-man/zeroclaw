"""Analytics Page.

This page provides comprehensive analytics and metrics visualization with interactive
charts organized into tabs for different analytical perspectives (Overview, Performance,
Errors, Usage). Uses Matrix Green theme throughout.
"""

import streamlit as st
from components import analytics
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

    # Delegations Tab: Agent delegation tree visualization
    with tab5:
        st.markdown("### Agent Delegations")
        st.caption("Visualize nested agent delegation hierarchies and execution status")

        # Delegation summary metrics
        delegation_tree.render_delegation_summary()

        st.divider()

        # Delegation tree visualization (now using real data from JSONL)
        delegation_tree.render_delegation_tree(use_mock_data=False)

        # Instructions for delegation tracking
        with st.expander("ℹ️ About Delegation Tracking"):
            st.markdown("""
            **✅ Phase 1 Delegation Visibility: COMPLETE**

            The delegation tracking system is now fully operational. This page displays
            real delegation events from the ZeroClaw backend in real-time.

            **How it works:**

            1. **Backend Integration** - `DelegationEventObserver` writes events to JSONL
            2. **Event Forwarding** - `ForwardingObserver` ensures child agent events are visible
            3. **Event Storage** - All delegation events stored in `~/.zeroclaw/state/delegation.jsonl`
            4. **UI Parsing** - This page reads and builds the delegation tree automatically

            **What you see:**

            - **Delegation Tree** - Hierarchical view of agent → sub-agent relationships
            - **Status Indicators** - 🟡 Running, ✅ Success, ❌ Failed
            - **Metrics** - Duration, depth, provider/model for each delegation
            - **Real-time Updates** - Page refreshes to show latest delegations

            **If you see "No delegation data found":**

            This means no delegations have occurred yet. Trigger a delegation by:
            - Using the `delegate` tool in your agent configuration
            - Running an agent workflow that includes sub-agent delegation
            - Starting the ZeroClaw backend and executing tasks that delegate work

            **Event Format (JSONL):**
            ```json
            {"event_type":"DelegationStart","agent_name":"research","provider":"anthropic","model":"claude-sonnet-4","depth":1,"agentic":true,"timestamp":"2026-02-21T10:30:45Z"}
            {"event_type":"DelegationEnd","agent_name":"research","provider":"anthropic","model":"claude-sonnet-4","depth":1,"duration_ms":4512,"success":true,"error_message":null,"timestamp":"2026-02-21T10:30:50Z"}
            ```
            """)


# Entry point for Streamlit multi-page app
if __name__ == "__main__":
    render()
