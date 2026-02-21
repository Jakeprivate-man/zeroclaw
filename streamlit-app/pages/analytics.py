"""Analytics Page.

This page provides comprehensive analytics and metrics visualization with interactive
charts organized into tabs for different analytical perspectives (Overview, Performance,
Errors, Usage). Uses Matrix Green theme throughout.
"""

import streamlit as st
from components import analytics
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
    tab1, tab2, tab3, tab4 = st.tabs([
        "Overview",
        "Performance",
        "Errors",
        "Usage"
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


# Entry point for Streamlit multi-page app
if __name__ == "__main__":
    render()
