"""RealTimeMetrics component for displaying live gateway metrics.

This component displays 4 metric cards with real-time updates and sparkline charts:
- Active Agents
- Requests Today
- CPU Usage (color-coded)
- Reports Generated

Each metric includes a trend indicator and a mini sparkline chart showing
recent history.
"""

import streamlit as st
import plotly.graph_objects as go
from typing import List, Dict, Any
from lib.session_state import get_state, update_gateway_state
from lib.mock_data import generate_gateway_stats


def render() -> None:
    """Render 4 real-time metric cards with sparklines.

    This is the main entry point for the RealTimeMetrics component.
    It creates a 4-column layout with metrics for:
    - Active Agents (with trend)
    - Requests Today (with trend)
    - CPU Usage (color-coded by threshold)
    - Reports Generated (with trend)

    Each metric includes a sparkline chart showing the last 20 data points.
    """
    # Get current stats from session state
    stats = get_state('gateway_stats')
    metrics_history = get_state('metrics_history', {})
    cpu_usage = get_state('cpu_usage', 0)

    # Update stats if not initialized (simulated real-time)
    if stats is None:
        stats = generate_gateway_stats()
        update_gateway_state(stats=stats)

    # Create 4-column layout
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Active Agents metric with sparkline
        active_agents = stats.get('active_agents', 0)
        history = metrics_history.get('active_agents', [])
        trend = calculate_trend(history)

        st.metric(
            "Active Agents",
            active_agents,
            delta=f"{trend:+.1f}%" if trend != 0 else None,
            delta_color="normal"
        )
        render_sparkline(history, "#5FAF87")

    with col2:
        # Requests Today metric
        requests = stats.get('requests_today', 0)
        history = metrics_history.get('requests_today', [])
        trend = calculate_trend(history)

        st.metric(
            "Requests Today",
            f"{requests:,}",
            delta=f"{trend:+.1f}%" if trend != 0 else None,
            delta_color="normal"
        )
        render_sparkline(history, "#87D7AF")

    with col3:
        # CPU Usage metric (color-coded)
        # delta_color "inverse" means red is bad, green is good
        delta_color = "inverse" if cpu_usage > 80 else "normal"

        st.metric(
            "CPU Usage",
            f"{cpu_usage:.0f}%",
            delta=None,
            delta_color=delta_color
        )

        # Color based on threshold: red >80%, yellow >60%, green otherwise
        color = "#FF5555" if cpu_usage > 80 else "#F1FA8C" if cpu_usage > 60 else "#5FAF87"
        history = metrics_history.get('cpu_usage', [])
        render_sparkline(history, color)

    with col4:
        # Reports Generated metric
        reports = stats.get('reports_generated', 0)
        history = metrics_history.get('reports_generated', [])
        trend = calculate_trend(history)

        st.metric(
            "Reports Generated",
            reports,
            delta=f"{trend:+.1f}%" if trend != 0 else None,
            delta_color="normal"
        )
        render_sparkline(history, "#5FAF87")


def calculate_trend(history: List[Dict[str, Any]]) -> float:
    """Calculate percentage trend from history.

    Compares the most recent value against the average of the previous
    2-3 values to determine the trend direction and magnitude.

    Args:
        history: List of historical data points with 'value', 'count', or 'percentage' key

    Returns:
        Percentage change (e.g., 5.2 for 5.2% increase, -3.1 for 3.1% decrease)
        Returns 0 if insufficient data
    """
    if not history or len(history) < 2:
        return 0

    # Take last 3 points for trend calculation
    recent = history[-3:]
    if len(recent) < 2:
        return 0

    # Extract value from data point (handles 'value', 'count', 'percentage' keys)
    def get_value(data_point: Dict[str, Any]) -> float:
        for key in ['value', 'count', 'percentage']:
            if key in data_point:
                return float(data_point[key])
        return 0.0

    # Calculate average of older values (all but the last one)
    old_avg = sum(get_value(h) for h in recent[:-1]) / (len(recent) - 1)

    # Get the newest value
    new_val = get_value(recent[-1])

    # Avoid division by zero
    if old_avg == 0:
        return 0

    # Calculate percentage change
    return ((new_val - old_avg) / old_avg) * 100


def render_sparkline(history: List[Dict[str, Any]], color: str) -> None:
    """Render a mini sparkline chart using Plotly.

    Creates a minimal line chart suitable for inline metric visualization.
    The chart shows the last 20 data points with no axes or labels,
    optimized for a compact display.

    Args:
        history: List of data points, each with 'value', 'count', or 'percentage' key
        color: Hex color string for the line (e.g., "#5FAF87")
    """
    if not history or len(history) == 0:
        # Render empty space to maintain layout
        st.markdown('<div style="height: 60px;"></div>', unsafe_allow_html=True)
        return

    # Extract value from data point (handles 'value', 'count', 'percentage' keys)
    def get_value(data_point: Dict[str, Any]) -> float:
        for key in ['value', 'count', 'percentage']:
            if key in data_point:
                return float(data_point[key])
        return 0.0

    # Extract values from history (last 20 points)
    values = [get_value(h) for h in history[-20:]]

    # Create Plotly figure
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=values,
        mode='lines',
        line=dict(color=color, width=2),
        showlegend=False,
        hoverinfo='skip'
    ))

    # Update layout for minimal sparkline appearance
    fig.update_layout(
        height=60,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode=False
    )

    # Render chart with config to hide mode bar
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={'displayModeBar': False}
    )


# Expose main render function as the public API
__all__ = ['render']
