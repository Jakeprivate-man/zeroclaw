"""Error Rate Chart Component.

This module provides an interactive Plotly chart showing error rate percentage over time.
Uses Matrix Green theme colors with preserved red (#FF5555) for the error rate line.
"""

import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_error_rate_data


def render() -> None:
    """Render error rate chart showing percentage over time.

    Displays an interactive line chart showing:
    - Error rate percentage over time (red line)

    Time range is controlled by session state 'time_range' variable.
    Uses Matrix Green theme colors for UI elements, with preserved
    red (#FF5555) for error rate line to indicate errors.
    """
    # Get time range from session state (default: 7d)
    time_range = get_state('time_range', '7d')

    # Generate mock data for the selected time range
    data = generate_error_rate_data(time_range)

    # Create Plotly figure
    fig = go.Figure()

    # Add error rate line (Preserved red for errors)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['error_rate'] for d in data],
        name='Error Rate',
        line=dict(color='#FF5555', width=2),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>Error Rate</b><br>' +
                      'Date: %{x}<br>' +
                      'Error Rate: %{y}%<br>' +
                      '<extra></extra>'
    ))

    # Update layout with Matrix Green theme
    fig.update_layout(
        title={
            'text': "Error Rate Over Time",
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
            title="Error Rate (%)",
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
