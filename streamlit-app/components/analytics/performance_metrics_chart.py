"""Performance Metrics Chart Component.

This module provides an interactive Plotly grouped bar chart showing performance latency
percentiles (p50, p95, p99) across different services and endpoints. Uses Matrix Green theme.
"""

import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_performance_metrics_data


def render() -> None:
    """Render performance metrics grouped bar chart.

    Displays an interactive grouped bar chart showing:
    - p50, p95, p99 latency percentiles for each service/endpoint
    - Color-coded bars (green shades for different percentiles)
    - Hover tooltips with exact latency values

    Time range is controlled by session state 'time_range' variable.
    Uses Matrix Green theme colors with distinct shades for each percentile:
    - p50: Light green (#87D7AF)
    - p95: Medium green (#66CDAA)
    - p99: Dark yellow/warning (#F1FA8C) to indicate high tail latency
    """
    # Get time range from session state (default: 7d)
    time_range = get_state('time_range', '7d')

    # Generate mock data for the selected time range
    data = generate_performance_metrics_data(time_range)

    # Extract categories and percentile values
    categories = [d['category'] for d in data]
    p50_values = [d['p50'] for d in data]
    p95_values = [d['p95'] for d in data]
    p99_values = [d['p99'] for d in data]

    # Create Plotly figure with grouped bars
    fig = go.Figure()

    # Add p50 bars (lightest green - best case)
    fig.add_trace(go.Bar(
        x=categories,
        y=p50_values,
        name='p50 (median)',
        marker=dict(
            color='#87D7AF',
            line=dict(color='#5FAF87', width=1)
        ),
        hovertemplate='<b>%{x}</b><br>' +
                      'p50: %{y}ms<br>' +
                      '<extra></extra>'
    ))

    # Add p95 bars (medium green)
    fig.add_trace(go.Bar(
        x=categories,
        y=p95_values,
        name='p95',
        marker=dict(
            color='#5FAF87',
            line=dict(color='#48D1CC', width=1)
        ),
        hovertemplate='<b>%{x}</b><br>' +
                      'p95: %{y}ms<br>' +
                      '<extra></extra>'
    ))

    # Add p99 bars (yellow warning - tail latency)
    fig.add_trace(go.Bar(
        x=categories,
        y=p99_values,
        name='p99 (tail)',
        marker=dict(
            color='#F1FA8C',
            line=dict(color='#E5E500', width=1)
        ),
        hovertemplate='<b>%{x}</b><br>' +
                      'p99: %{y}ms<br>' +
                      '<extra></extra>'
    ))

    # Update layout with Matrix Green theme
    fig.update_layout(
        title={
            'text': "Performance Latency Percentiles",
            'font': {'size': 20, 'color': '#87D7AF'}
        },
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        xaxis=dict(
            title="Service / Endpoint",
            showgrid=False,
            linecolor='#5FAF87',
            tickangle=-45
        ),
        yaxis=dict(
            title="Latency (ms)",
            showgrid=True,
            gridcolor='#1a1a1a',
            linecolor='#5FAF87'
        ),
        barmode='group',
        bargap=0.15,
        bargroupgap=0.1,
        height=400,
        margin=dict(l=60, r=50, t=80, b=120),  # Extra bottom margin for rotated labels
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
        hoverlabel=dict(
            bgcolor="#000000",
            font_size=12,
            font_family="monospace",
            bordercolor="#5FAF87"
        )
    )

    # Display chart in Streamlit
    st.plotly_chart(fig, use_container_width=True)
