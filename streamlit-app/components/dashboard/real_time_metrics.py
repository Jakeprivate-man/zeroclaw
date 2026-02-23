"""RealTimeMetrics component for displaying live metrics from ZeroClaw state files.

This component displays 4 metric cards with real data:
- Configured Agents (from config.toml)
- Session Requests (from costs.jsonl)
- Total Tokens (from costs.jsonl)
- Session Cost (from costs.jsonl)

Shows honest empty states when no data is available.
"""

import streamlit as st
from lib.costs_parser import costs_parser
from lib.agent_monitor import agent_monitor


def render() -> None:
    """Render real-time metric cards from actual data sources.

    Displays metrics derived from real ZeroClaw state files:
    - Configured Agents (from config.toml)
    - Session Requests (from costs.jsonl)
    - Total Tokens (from costs.jsonl)
    - Session Cost (from costs.jsonl)

    Shows honest empty states when no data is available.
    """
    # Try to get real data from costs.jsonl
    has_cost_data = costs_parser.file_exists()

    if has_cost_data:
        try:
            summary = costs_parser.get_cost_summary()
        except Exception:
            summary = None
    else:
        summary = None

    # Get agent count from real config
    try:
        agent_count = agent_monitor.get_agent_count()
    except Exception:
        agent_count = 0

    # Create 4-column layout
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Configured Agents",
            agent_count,
            help="Number of agents defined in config.toml"
        )

    with col2:
        if summary:
            request_count = summary.get("request_count", 0)
            st.metric(
                "Session Requests",
                f"{request_count:,}",
                help="API requests in the current session (from costs.jsonl)"
            )
        else:
            st.metric("Session Requests", "--")
            st.caption("No data yet")

    with col3:
        if summary:
            total_tokens = summary.get("total_tokens", 0)
            st.metric(
                "Total Tokens",
                f"{total_tokens:,}",
                help="Total tokens used in the current session"
            )
        else:
            st.metric("Total Tokens", "--")
            st.caption("No data yet")

    with col4:
        if summary:
            session_cost = summary.get("session_cost_usd", 0.0)
            st.metric(
                "Session Cost",
                f"${session_cost:.4f}",
                help="Cost for the current session"
            )
        else:
            st.metric("Session Cost", "--")
            st.caption("No data yet")

    if not has_cost_data:
        st.info("No cost data yet -- start ZeroClaw to see live metrics here.")


# Expose main render function as the public API
__all__ = ['render']
