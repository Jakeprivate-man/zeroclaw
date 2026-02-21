"""Feature Usage Chart Component.

This module provides an interactive Plotly horizontal bar chart showing feature usage
distribution across different system capabilities. Uses Matrix Green theme colors.
"""

import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_feature_usage_data


def render() -> None:
    """Render feature usage horizontal bar chart.

    Displays an interactive horizontal bar chart showing:
    - Feature name and usage count
    - Percentage of total usage
    - Sorted by usage count (descending)

    Time range is controlled by session state 'time_range' variable.
    Uses Matrix Green theme colors (#5FAF87, #87D7AF) with gradient
    coloring based on usage percentage.
    """
    # Get time range from session state (default: 7d)
    time_range = get_state('time_range', '7d')

    # Generate mock data for the selected time range
    data = generate_feature_usage_data(time_range)

    # Create color gradient based on usage percentage
    # Darker green for higher usage, lighter for lower usage
    colors = []
    for item in data:
        # Interpolate between light and dark green based on percentage
        pct = item['percentage']
        if pct >= 20:
            colors.append('#5FAF87')  # Primary green for high usage
        elif pct >= 10:
            colors.append('#87D7AF')  # Sea green for medium usage
        elif pct >= 5:
            colors.append('#66CDAA')  # Turquoise for moderate usage
        else:
            colors.append('#48D1CC')  # Light turquoise for low usage

    # Create Plotly figure with horizontal bars
    fig = go.Figure()

    # Add horizontal bar chart
    fig.add_trace(go.Bar(
        y=[d['feature'] for d in data],
        x=[d['usage_count'] for d in data],
        orientation='h',
        marker=dict(
            color=colors,
            line=dict(color='#5FAF87', width=1)
        ),
        text=[f"{d['percentage']}%" for d in data],
        textposition='outside',
        textfont=dict(color='#87D7AF', size=11),
        hovertemplate='<b>%{y}</b><br>' +
                      'Usage: %{x:,}<br>' +
                      'Percentage: %{text}<br>' +
                      '<extra></extra>',
        showlegend=False
    ))

    # Update layout with Matrix Green theme
    fig.update_layout(
        title={
            'text': "Feature Usage Distribution",
            'font': {'size': 20, 'color': '#87D7AF'}
        },
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        xaxis=dict(
            title="Usage Count",
            showgrid=True,
            gridcolor='#1a1a1a',
            linecolor='#5FAF87',
            tickformat=','
        ),
        yaxis=dict(
            title="",  # No y-axis title needed for feature names
            showgrid=False,
            linecolor='#5FAF87',
            categoryorder='total ascending'  # Already sorted in data
        ),
        height=400,
        margin=dict(l=150, r=100, t=80, b=50),  # Extra left margin for feature names
        hoverlabel=dict(
            bgcolor="#000000",
            font_size=12,
            font_family="monospace",
            bordercolor="#5FAF87"
        )
    )

    # Display chart in Streamlit
    st.plotly_chart(fig, use_container_width=True)
