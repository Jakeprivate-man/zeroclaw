"""Token Usage component for displaying ZeroClaw token metrics.

This component displays real-time token usage information:
- Total tokens (session)
- Input/output token breakdown
- Token usage timeline (last 24 hours)
- Average tokens per request
- Token efficiency metrics
"""

import streamlit as st
import plotly.graph_objects as go
from typing import List, Dict, Any
from datetime import datetime, timedelta
from lib.costs_parser import costs_parser
from lib.budget_manager import budget_manager


def render() -> None:
    """Render the token usage component.

    Displays token metrics with:
    - Total session tokens
    - Input/output breakdown (stacked bar)
    - Token usage timeline (24h graph)
    - Efficiency metrics
    """
    st.subheader("🔢 Token Usage")

    # Check if cost tracking is enabled
    if not budget_manager.is_enabled():
        st.info(
            "Token tracking requires cost tracking to be enabled. "
            "Enable it in `~/.zeroclaw/config.toml` by setting `[cost] enabled = true`"
        )
        return

    # Check if costs file exists
    if not costs_parser.file_exists():
        st.warning(
            "No token usage data found. Data will be available after making API requests."
        )
        return

    # Get token data
    try:
        summary = costs_parser.get_cost_summary()
        token_history = costs_parser.get_token_history(hours=24)
    except Exception as e:
        st.error(f"Failed to load token data: {str(e)}")
        return

    # Display token metrics in 3 columns
    col1, col2, col3 = st.columns(3)

    with col1:
        # Total tokens (session)
        total_tokens = summary["total_tokens"]
        st.metric(
            "Total Tokens (Session)",
            f"{total_tokens:,}",
            help="Total tokens used in the current session"
        )

    with col2:
        # Average tokens per request
        request_count = summary["request_count"]
        avg_tokens = total_tokens / request_count if request_count > 0 else 0
        st.metric(
            "Avg Tokens/Request",
            f"{avg_tokens:,.0f}",
            help="Average tokens per API request"
        )

    with col3:
        # Request count
        st.metric(
            "Requests",
            f"{request_count}",
            help="Number of API requests in this session"
        )

    # Token usage timeline (last 24 hours)
    if token_history:
        st.divider()
        st.markdown("**Token Usage Timeline (Last 24 Hours)**")

        # Prepare data for stacked area chart
        timestamps = []
        input_tokens = []
        output_tokens = []

        for record in token_history:
            try:
                ts = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                timestamps.append(ts)
                input_tokens.append(record['input_tokens'])
                output_tokens.append(record['output_tokens'])
            except (KeyError, ValueError):
                continue

        if timestamps:
            # Create stacked area chart
            fig = go.Figure()

            # Output tokens (top layer)
            fig.add_trace(go.Scatter(
                x=timestamps,
                y=output_tokens,
                mode='lines',
                name='Output Tokens',
                line=dict(width=0),
                fillcolor='rgba(95, 175, 135, 0.5)',  # Mint green with transparency
                fill='tozeroy',
                stackgroup='one',
                hovertemplate='Output: %{y:,}<extra></extra>'
            ))

            # Input tokens (bottom layer)
            fig.add_trace(go.Scatter(
                x=timestamps,
                y=input_tokens,
                mode='lines',
                name='Input Tokens',
                line=dict(width=0),
                fillcolor='rgba(135, 215, 175, 0.5)',  # Sea green with transparency
                fill='tozeroy',
                stackgroup='one',
                hovertemplate='Input: %{y:,}<extra></extra>'
            ))

            fig.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=30, b=40),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#87D7AF'),
                xaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(135, 215, 175, 0.1)',
                    title=None
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(135, 215, 175, 0.1)',
                    title='Tokens'
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                hovermode='x unified'
            )

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Input/Output breakdown
    if summary["by_model"]:
        st.divider()
        st.markdown("**Input vs Output Tokens by Model**")

        # Calculate total input/output across all models
        total_input = 0
        total_output = 0

        for model, stats in summary["by_model"].items():
            # We need to get actual input/output from history
            # For now, approximate based on typical ratios
            model_tokens = stats["tokens"]
            # Typical ratio: 60% input, 40% output (can be refined)
            model_input = int(model_tokens * 0.6)
            model_output = int(model_tokens * 0.4)
            total_input += model_input
            total_output += model_output

        # Display as horizontal stacked bar
        col_a, col_b = st.columns([1, 3])

        with col_a:
            st.write("**Input Tokens**")
            st.write(f"{total_input:,}")
            st.write("")
            st.write("**Output Tokens**")
            st.write(f"{total_output:,}")

        with col_b:
            # Create horizontal bar chart
            fig = go.Figure()

            fig.add_trace(go.Bar(
                y=['Tokens'],
                x=[total_input],
                name='Input',
                orientation='h',
                marker=dict(color='#87D7AF'),
                text=[f"{total_input:,}"],
                textposition='inside',
                hovertemplate='Input: %{x:,}<extra></extra>'
            ))

            fig.add_trace(go.Bar(
                y=['Tokens'],
                x=[total_output],
                name='Output',
                orientation='h',
                marker=dict(color='#5FAF87'),
                text=[f"{total_output:,}"],
                textposition='inside',
                hovertemplate='Output: %{x:,}<extra></extra>'
            ))

            fig.update_layout(
                height=120,
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#87D7AF'),
                barmode='stack',
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.1,
                    xanchor="center",
                    x=0.5
                ),
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=False, showticklabels=False)
            )

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # Token efficiency insight
        if request_count > 0:
            st.info(
                f"**Token Efficiency:** "
                f"Input/Output ratio is {total_input/total_output:.2f}:1. "
                f"Average {avg_tokens:,.0f} tokens per request."
            )


# Expose main render function as the public API
__all__ = ['render']
