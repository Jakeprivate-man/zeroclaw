"""Request Distribution Chart Component.

Shows distribution of agent delegations by model, derived from real
DelegationStart events in ~/.zeroclaw/state/delegation.jsonl. Displays an
honest empty state when no delegation data is available.
"""

import streamlit as st
import plotly.graph_objects as go
from collections import Counter
from lib.delegation_parser import DelegationParser


def render() -> None:
    """Render delegation distribution donut chart from real data.

    Groups DelegationStart events by model and shows their relative
    frequency as a donut chart. Falls back to an informative empty state.
    """
    parser = DelegationParser()
    events = parser._read_events()

    starts = [e for e in events if e.get("event_type") == "DelegationStart"]

    if not starts:
        st.info(
            "No delegation data available. "
            "Run ZeroClaw with agent delegation workflows to populate this chart."
        )
        return

    # Count delegations by model
    model_counts = Counter(s.get("model", "unknown") for s in starts)
    models = list(model_counts.keys())
    counts = list(model_counts.values())

    colors = [
        "#5FAF87", "#87D7AF", "#87D787", "#5FD7AF",
        "#5FD7D7", "#87AFAF", "#5FAFAF", "#87D7D7",
    ]

    fig = go.Figure()

    fig.add_trace(go.Pie(
        labels=models,
        values=counts,
        marker=dict(colors=colors[:len(models)], line=dict(color="#000000", width=2)),
        textinfo="percent",
        textfont=dict(size=12, color="#ffffff", family="monospace"),
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>",
        hole=0.4,
    ))

    fig.update_layout(
        title={"text": "Delegation Distribution by Model", "font": {"size": 20, "color": "#87D7AF"}, "x": 0.5, "xanchor": "center"},
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        height=400,
        showlegend=True,
        legend=dict(
            orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05,
            bgcolor="rgba(0,0,0,0.5)", bordercolor="#5FAF87", borderwidth=1,
            font=dict(size=11),
        ),
        margin=dict(l=50, r=150, t=80, b=50),
    )

    st.plotly_chart(fig, use_container_width=True)
