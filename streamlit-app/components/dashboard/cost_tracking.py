"""Cost Tracking component for displaying ZeroClaw cost metrics.

This component displays real-time cost information from the costs.jsonl file:
- Session cost (current session total)
- Daily cost (today's total with budget %)
- Monthly cost (this month's total with budget %)
- Budget status alerts
- Cost breakdown by model (pie chart)
"""

import streamlit as st
import plotly.graph_objects as go
from typing import Dict, Any
from lib.costs_parser import costs_parser
from lib.budget_manager import budget_manager, BudgetStatus


def render() -> None:
    """Render the cost tracking component.

    Displays cost metrics in a 3-column layout with:
    - Session cost
    - Daily cost with budget indicator
    - Monthly cost with budget indicator
    - Budget alerts (if warning or exceeded)
    - Cost breakdown by model (pie chart)
    """
    st.subheader("💰 Cost Tracking")

    # Check if cost tracking is enabled
    if not budget_manager.is_enabled():
        st.info(
            "Cost tracking is currently disabled. "
            "Enable it in `~/.zeroclaw/config.toml` by setting `[cost] enabled = true`"
        )
        return

    # Check if costs file exists
    if not costs_parser.file_exists():
        st.warning(
            "No cost data found. The costs.jsonl file will be created at "
            "`~/.zeroclaw/state/costs.jsonl` when you start making API requests."
        )
        return

    # Get cost summary and budget status
    try:
        summary = costs_parser.get_cost_summary()
        budget_summary = budget_manager.get_budget_summary()
    except Exception as e:
        st.error(f"Failed to load cost data: {str(e)}")
        return

    # Display cost metrics in 3 columns
    col1, col2, col3 = st.columns(3)

    with col1:
        # Session cost
        session_cost = summary["session_cost_usd"]
        st.metric(
            "Session Cost",
            f"${session_cost:.4f}",
            help="Cost for the current session"
        )

    with col2:
        # Daily cost with budget indicator
        daily_check = budget_summary["daily"]
        daily_cost = daily_check["current_usd"]
        daily_limit = daily_check["limit_usd"]
        daily_pct = daily_check["percent_used"]

        delta_str = f"{daily_pct:.0f}% of ${daily_limit:.2f}"
        delta_color = _get_delta_color(daily_check["status"])

        st.metric(
            "Daily Cost",
            f"${daily_cost:.4f}",
            delta=delta_str,
            delta_color=delta_color,
            help=f"Cost for today (limit: ${daily_limit:.2f})"
        )

    with col3:
        # Monthly cost with budget indicator
        monthly_check = budget_summary["monthly"]
        monthly_cost = monthly_check["current_usd"]
        monthly_limit = monthly_check["limit_usd"]
        monthly_pct = monthly_check["percent_used"]

        delta_str = f"{monthly_pct:.0f}% of ${monthly_limit:.2f}"
        delta_color = _get_delta_color(monthly_check["status"])

        st.metric(
            "Monthly Cost",
            f"${monthly_cost:.4f}",
            delta=delta_str,
            delta_color=delta_color,
            help=f"Cost for this month (limit: ${monthly_limit:.2f})"
        )

    # Budget alerts
    daily_alert = budget_manager.format_budget_alert("daily")
    monthly_alert = budget_manager.format_budget_alert("monthly")

    if daily_check["status"] == BudgetStatus.EXCEEDED:
        st.error(daily_alert)
    elif daily_check["status"] == BudgetStatus.WARNING:
        st.warning(daily_alert)

    if monthly_check["status"] == BudgetStatus.EXCEEDED:
        st.error(monthly_alert)
    elif monthly_check["status"] == BudgetStatus.WARNING:
        st.warning(monthly_alert)

    # Cost breakdown by model
    if summary["by_model"]:
        st.divider()
        st.markdown("**Cost Breakdown by Model**")

        # Create pie chart
        labels = []
        values = []
        colors = _get_model_colors(len(summary["by_model"]))

        for model, stats in summary["by_model"].items():
            # Shorten model name for display
            model_short = model.split("/")[-1] if "/" in model else model
            labels.append(model_short)
            values.append(stats["cost_usd"])

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker=dict(colors=colors),
            hole=0.3,  # Donut chart
            textposition='auto',
            textinfo='label+percent',
            hovertemplate='%{label}<br>$%{value:.4f}<br>%{percent}<extra></extra>'
        )])

        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=30, b=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#87D7AF'),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5
            )
        )

        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # Show detailed breakdown in expandable section
        with st.expander("View Detailed Breakdown"):
            for model, stats in summary["by_model"].items():
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.write(f"**{model}**")
                with col_b:
                    st.write(f"${stats['cost_usd']:.4f}")
                with col_c:
                    st.write(f"{stats['tokens']:,} tokens ({stats['requests']} requests)")


def _get_delta_color(status: BudgetStatus) -> str:
    """Get Streamlit delta color based on budget status.

    Args:
        status: Budget status

    Returns:
        "normal" for allowed, "off" for warning/exceeded
    """
    if status == BudgetStatus.EXCEEDED or status == BudgetStatus.WARNING:
        return "off"  # Disable color to avoid confusion
    return "normal"


def _get_model_colors(count: int) -> list:
    """Get a list of Matrix-themed colors for model breakdown.

    Args:
        count: Number of colors needed

    Returns:
        List of hex color strings
    """
    # Matrix green palette (from light to dark)
    palette = [
        "#5FAF87",  # Mint green
        "#87D7AF",  # Sea green
        "#5FD7AF",  # Turquoise
        "#87FFAF",  # Light aqua
        "#5FD787",  # Medium green
        "#87D787",  # Sage green
    ]

    # Cycle through palette if more colors needed
    colors = []
    for i in range(count):
        colors.append(palette[i % len(palette)])

    return colors


# Expose main render function as the public API
__all__ = ['render']
