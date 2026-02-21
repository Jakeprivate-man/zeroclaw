"""Error Types Chart Component.

This module provides an interactive Plotly bar chart showing error types breakdown
by HTTP status code. Uses red and yellow shades to indicate errors and warnings,
following the Matrix Green theme error color scheme.
"""

import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_error_types_data


def render() -> None:
    """Render error types chart as an interactive horizontal bar chart.

    Displays a bar chart showing:
    - Breakdown of different error types by HTTP status code
    - Error count and percentage for each type
    - Interactive hover tooltips with details
    - Color-coded bars (red for 5xx, yellow for 4xx, orange for timeouts/rate limits)

    Time range is controlled by session state 'time_range' variable.
    Uses red/yellow/orange shades to indicate different error severity levels,
    following Matrix Green theme error color scheme (#FF5555 for errors, #F1FA8C for warnings).
    """
    # Get time range from session state (default: 7d)
    time_range = get_state('time_range', '7d')

    # Generate mock data for the selected time range
    data = generate_error_types_data(time_range)

    # Extract error types, counts, percentages, and status codes
    error_types = [item['error_type'] for item in data]
    counts = [item['count'] for item in data]
    percentages = [item['percentage'] for item in data]
    status_codes = [item['status_code'] for item in data]

    # Define color mapping based on HTTP status code
    # 5xx = Red (server errors), 4xx = Yellow (client errors), timeout/rate limit = Orange
    def get_error_color(status_code: int) -> str:
        """Map HTTP status code to error color."""
        if status_code >= 500:
            # Server errors (5xx) - Red shades
            return '#FF5555'  # Primary red for errors
        elif status_code in [408, 429]:
            # Timeout/rate limit errors - Orange
            return '#FFB86C'  # Orange for special cases
        elif status_code >= 400:
            # Client errors (4xx) - Yellow shades
            return '#F1FA8C'  # Yellow for warnings
        else:
            # Fallback - Light red
            return '#FF6E6E'

    # Assign colors to each error type
    colors = [get_error_color(code) for code in status_codes]

    # Create Plotly horizontal bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=error_types,
        x=counts,
        orientation='h',
        marker=dict(
            color=colors,
            line=dict(color='#000000', width=1)
        ),
        text=[f"{pct}%" for pct in percentages],
        textposition='outside',
        textfont=dict(size=11, color='#87D7AF', family='monospace'),
        hovertemplate='<b>%{y}</b><br>' +
                      'Count: %{x}<br>' +
                      'Percentage: %{text}<br>' +
                      '<extra></extra>',
        customdata=status_codes,
        name='Error Count'
    ))

    # Update layout with Matrix Green theme
    fig.update_layout(
        title={
            'text': "Error Types by HTTP Status Code",
            'font': {'size': 20, 'color': '#87D7AF'},
            'x': 0.5,
            'xanchor': 'center'
        },
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        xaxis=dict(
            title="Error Count",
            showgrid=True,
            gridcolor='#1a1a1a',
            linecolor='#5FAF87',
            tickfont=dict(size=11)
        ),
        yaxis=dict(
            title="",
            showgrid=False,
            linecolor='#5FAF87',
            tickfont=dict(size=11),
            autorange='reversed'  # Top to bottom order
        ),
        height=400,
        showlegend=False,
        margin=dict(l=200, r=80, t=80, b=50),
        hoverlabel=dict(
            bgcolor="#000000",
            font_size=12,
            font_family="monospace",
            bordercolor="#FF5555"
        )
    )

    # Display chart in Streamlit
    st.plotly_chart(fig, use_container_width=True)
