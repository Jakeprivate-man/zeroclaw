"""User Activity Chart Component.

This module provides an interactive Plotly chart showing user activity metrics over time,
including active users, new users, and returning users. Uses Matrix Green theme colors.
"""

import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_user_activity_data


def render() -> None:
    """Render user activity chart with active/new/returning users breakdown.

    Displays an interactive area chart showing:
    - Total active users (primary green area)
    - New users (sea green line)
    - Returning users (turquoise line)

    Time range is controlled by session state 'time_range' variable.
    Uses Matrix Green theme colors (#5FAF87, #87D7AF) and variations
    for a cohesive multi-series visualization.
    """
    # Get time range from session state (default: 7d)
    time_range = get_state('time_range', '7d')

    # Generate mock data for the selected time range
    data = generate_user_activity_data(time_range)

    # Enhance data with new/returning user breakdown
    # Split active users into ~30% new, ~70% returning with some variance
    for point in data:
        active = point['active_users']
        # New users: 25-35% of active users
        new_users = int(active * (0.25 + (hash(str(point['timestamp'])) % 10) / 100))
        point['new_users'] = new_users
        point['returning_users'] = active - new_users

    # Create Plotly figure
    fig = go.Figure()

    # Add total active users as area chart (Matrix Green primary color)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['active_users'] for d in data],
        name='Active Users',
        line=dict(color='#5FAF87', width=2),
        fill='tozeroy',
        fillcolor='rgba(95, 175, 135, 0.3)',
        mode='lines',
        hovertemplate='<b>Active Users</b><br>' +
                      'Date: %{x}<br>' +
                      'Users: %{y}<br>' +
                      '<extra></extra>'
    ))

    # Add new users line (Sea green)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['new_users'] for d in data],
        name='New Users',
        line=dict(color='#87D7AF', width=2),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>New Users</b><br>' +
                      'Date: %{x}<br>' +
                      'Users: %{y}<br>' +
                      '<extra></extra>'
    ))

    # Add returning users line (Turquoise/Aqua green)
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['returning_users'] for d in data],
        name='Returning Users',
        line=dict(color='#66CDAA', width=2),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>Returning Users</b><br>' +
                      'Date: %{x}<br>' +
                      'Users: %{y}<br>' +
                      '<extra></extra>'
    ))

    # Update layout with Matrix Green theme
    fig.update_layout(
        title={
            'text': "User Activity Over Time",
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
            title="Users",
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
