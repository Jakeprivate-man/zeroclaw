"""Request Distribution Chart Component.

This module provides an interactive Plotly pie/donut chart showing request distribution
by category or type. Uses Matrix Green theme colors with distinct shades for each category.
"""

import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_request_distribution_data


def render() -> None:
    """Render request distribution chart as an interactive pie/donut chart.

    Displays a pie chart showing:
    - Distribution of different request types/categories
    - Count and percentage for each category
    - Interactive hover tooltips with details
    - Legend with category labels

    Time range is controlled by session state 'time_range' variable.
    Uses Matrix Green theme colors with various green/turquoise shades for categories.
    """
    # Get time range from session state (default: 7d)
    time_range = get_state('time_range', '7d')

    # Generate mock data for the selected time range
    data = generate_request_distribution_data(time_range)

    # Extract categories, counts, and percentages
    categories = [item['category'] for item in data]
    counts = [item['count'] for item in data]
    percentages = [item['percentage'] for item in data]

    # Define Matrix Green theme color palette with variations
    # Uses various shades of green, turquoise, and aqua
    colors = [
        '#5FAF87',  # Mint green (primary)
        '#87D7AF',  # Sea green (secondary)
        '#87D787',  # Light green
        '#5FD7AF',  # Turquoise green
        '#5FD7D7',  # Cyan
        '#87AFAF',  # Muted green-gray
        '#5FAFAF',  # Teal
        '#87D7D7',  # Light cyan
    ]

    # Create Plotly pie chart
    fig = go.Figure()

    fig.add_trace(go.Pie(
        labels=categories,
        values=counts,
        marker=dict(
            colors=colors,
            line=dict(color='#000000', width=2)
        ),
        textinfo='percent',
        textfont=dict(size=12, color='#ffffff', family='monospace'),
        hovertemplate='<b>%{label}</b><br>' +
                      'Count: %{value}<br>' +
                      'Percentage: %{percent}<br>' +
                      '<extra></extra>',
        hole=0.4,  # Donut chart (0 for full pie, >0 for donut)
        pull=[0.05] + [0] * (len(categories) - 1)  # Slightly pull out the first slice
    ))

    # Update layout with Matrix Green theme
    fig.update_layout(
        title={
            'text': "Request Distribution by Type",
            'font': {'size': 20, 'color': '#87D7AF'},
            'x': 0.5,
            'xanchor': 'center'
        },
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        height=400,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05,
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor="#5FAF87",
            borderwidth=1,
            font=dict(size=11)
        ),
        margin=dict(l=50, r=150, t=80, b=50)
    )

    # Display chart in Streamlit
    st.plotly_chart(fig, use_container_width=True)
