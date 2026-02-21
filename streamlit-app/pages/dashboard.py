"""Dashboard page - orchestrates all dashboard components.

This is the main dashboard page that displays:
- RealTimeMetrics: 4 metric cards with sparklines (Active Agents, Requests, CPU, Reports)
- QuickActionsPanel: 16 action buttons organized by category
- CostTracking: Real-time cost monitoring (session/daily/monthly) [PHASE 1]
- TokenUsage: Token usage metrics and timeline [PHASE 1]
- AgentConfigStatus: Agent configuration and status [PHASE 1]
- ActivityStream: Live feed of system events (left column)
- AgentStatusMonitor: Individual agent health cards (right column)

The layout matches the React dashboard with proper vertical spacing and
responsive 2-column layout for the bottom section.
"""

import streamlit as st
from components.dashboard.real_time_metrics import render as render_metrics
from components.dashboard.quick_actions_panel import render as render_actions
from components.dashboard.cost_tracking import render as render_cost_tracking
from components.dashboard.token_usage import render as render_token_usage
from components.dashboard.agent_config_status import render as render_agent_config
from components.dashboard.activity_stream import render as render_activity
from components.dashboard.agent_status_monitor import render as render_agents


def render():
    """Render the complete Dashboard page.

    Layout structure:
    1. Page header with title and caption
    2. RealTimeMetrics component (4 metric cards with sparklines)
    3. QuickActionsPanel component (16 action buttons)
    4. Phase 1 Components - Cost & Token Tracking:
       - CostTracking: Session/daily/monthly costs with budget alerts
       - TokenUsage: Token usage timeline and metrics
       - AgentConfigStatus: Agent configuration and status
    5. Two-column layout:
       - Left: ActivityStream (live event feed)
       - Right: AgentStatusMonitor (agent health cards)

    Each section is separated by dividers for visual clarity.
    """
    # Page header
    st.title("📊 Dashboard")
    st.caption("Real-time monitoring of ZeroClaw agent activity and system health")

    st.divider()

    # Real-Time Metrics - 4 metric cards with sparklines
    render_metrics()

    st.divider()

    # Quick Actions Panel - 16 action buttons
    render_actions()

    st.divider()

    # === PHASE 1: Cost & Token Tracking ===
    # Cost Tracking - Session/daily/monthly costs with budget enforcement
    render_cost_tracking()

    st.divider()

    # Token Usage - Token metrics and timeline
    render_token_usage()

    st.divider()

    # Agent Configuration Status - Agent info and configuration
    render_agent_config()

    st.divider()

    # Activity Stream and Agent Status - Side by side
    col1, col2 = st.columns(2)

    with col1:
        # Activity Stream - Live feed of system events
        render_activity()

    with col2:
        # Agent Status Monitor - Individual agent health
        render_agents()


# Expose main render function as the public API
__all__ = ['render']
