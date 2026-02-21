"""Request Volume Chart Component.

This module provides an interactive Plotly chart showing request volume over time,
with successful vs failed request breakdown. Uses Matrix Green theme colors.
"""

import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_request_volume_data


def render() -> None:
    """Render request volume chart with successful/failed breakdown.

    Displays an interactive line chart showing:
    - Total request volume over time
    - Successful requests (green line)
    - Failed requests (red line)

    Time range is controlled by session state 'time_range' variable.
    Uses Matrix Green theme colors (#5FAF87, #87D7AF) with preserved
    red (#FF5555) for failed requests.
    """
    # Get time range from session state (default: 7d)
    time_range = get_state('time_range', '7d')

    # Generate mock data for the selected time range
    data = generate_request_volume_data(time_range)

    # Create Plotly figure
    fig = go.Figure()

    # Add successful requests line (Matrix Green primary color)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['successful'] for d in data],
        name='Successful',
        line=dict(color='#5FAF87', width=2),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>Successful</b><br>' +
                      'Date: %{x}<br>' +
                      'Requests: %{y}<br>' +
                      '<extra></extra>'
    ))

    # Add failed requests line (Preserved red for errors)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['failed'] for d in data],
        name='Failed',
        line=dict(color='#FF5555', width=2),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>Failed</b><br>' +
                      'Date: %{x}<br>' +
                      'Requests: %{y}<br>' +
                      '<extra></extra>'
    ))

    # Update layout with Matrix Green theme
    fig.update_layout(
        title={
            'text': "Request Volume Over Time",
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
            title="Requests",
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
