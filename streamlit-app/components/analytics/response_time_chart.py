"""Response Time Chart Component.

This module provides an interactive Plotly chart showing response time metrics over time,
including average, p50, p95, and p99 percentiles. Uses Matrix Green theme colors.
"""

import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_response_time_data


def render() -> None:
    """Render response time chart with percentile breakdown.

    Displays an interactive line chart showing:
    - Average response time (primary green line)
    - p50 (median) response time (sea green line)
    - p95 response time (yellow line for warning threshold)
    - p99 response time (red line for critical threshold)

    Time range is controlled by session state 'time_range' variable.
    Uses Matrix Green theme colors (#5FAF87, #87D7AF) with preserved
    yellow (#F1FA8C) for p95 and red (#FF5555) for p99.
    """
    # Get time range from session state (default: 7d)
    time_range = get_state('time_range', '7d')

    # Generate mock data for the selected time range
    data = generate_response_time_data(time_range)

    # Create Plotly figure
    fig = go.Figure()

    # Add average response time line (Matrix Green primary color)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['avg'] for d in data],
        name='Average',
        line=dict(color='#5FAF87', width=2),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>Average</b><br>' +
                      'Date: %{x}<br>' +
                      'Response Time: %{y}ms<br>' +
                      '<extra></extra>'
    ))

    # Add p50 (median) response time line (Sea green)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['p50'] for d in data],
        name='p50 (Median)',
        line=dict(color='#87D7AF', width=2),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>p50 (Median)</b><br>' +
                      'Date: %{x}<br>' +
                      'Response Time: %{y}ms<br>' +
                      '<extra></extra>'
    ))

    # Add p95 response time line (Yellow for warning)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['p95'] for d in data],
        name='p95',
        line=dict(color='#F1FA8C', width=2),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>p95</b><br>' +
                      'Date: %{x}<br>' +
                      'Response Time: %{y}ms<br>' +
                      '<extra></extra>'
    ))

    # Add p99 response time line (Red for critical)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['p99'] for d in data],
        name='p99',
        line=dict(color='#FF5555', width=2),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>p99</b><br>' +
                      'Date: %{x}<br>' +
                      'Response Time: %{y}ms<br>' +
                      '<extra></extra>'
    ))

    # Update layout with Matrix Green theme
    fig.update_layout(
        title={
            'text': "Response Time Percentiles Over Time",
            'font': {'size': 20, 'color': '#87D7AF'}
        },
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        xaxis=dict(
            title="Date",
            showgrid=True,
            gridcolor='#1a1a1a',
            linecolor='#5FAF87'
        ),
        yaxis=dict(
            title="Response Time (ms)",
            showgrid=True,
            gridcolor='#1a1a1a',
            linecolor='#5FAF87'
        ),
        height=400,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor="#5FAF87",
            borderwidth=1
        ),
        margin=dict(l=50, r=50, t=80, b=50)
    )

    # Display chart in Streamlit
    st.plotly_chart(fig, use_container_width=True)
