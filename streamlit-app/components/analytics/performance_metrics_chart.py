"""Performance Metrics Chart Component.

Shows delegation duration percentiles (p50, p95, p99) grouped by agent,
derived from real DelegationEnd events in ~/.zeroclaw/state/delegation.jsonl.
Displays an honest empty state when no duration data is available.
"""

import streamlit as st
import plotly.graph_objects as go
from collections import defaultdict
from lib.delegation_parser import DelegationParser


def _percentile(sorted_values, p):
    """Compute the p-th percentile from a sorted list."""
    if not sorted_values:
        return 0
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_values):
        return sorted_values[f]
    return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])


def render() -> None:
    """Render delegation latency percentiles grouped by agent.

    Reads DelegationEnd events with duration_ms, groups by agent_name,
    computes p50/p95/p99 percentiles, and shows a grouped bar chart.
    Falls back to empty state when no data is present.
    """
    parser = DelegationParser()
    events = parser._read_events()

    ends = [
        e for e in events
        if e.get("event_type") == "DelegationEnd" and e.get("duration_ms") is not None
    ]

    if not ends:
        st.info(
            "Performance metrics not available. "
            "Run ZeroClaw with agent delegation workflows to populate this chart."
        )
        return

    # Group durations by agent
    durations_by_agent = defaultdict(list)
    for e in ends:
        agent = e.get("agent_name", "unknown")
        durations_by_agent[agent].append(e["duration_ms"])

    # Sort durations and compute percentiles
    agents = sorted(durations_by_agent.keys())
    p50_vals = []
    p95_vals = []
    p99_vals = []

    for agent in agents:
        vals = sorted(durations_by_agent[agent])
        p50_vals.append(round(_percentile(vals, 50), 1))
        p95_vals.append(round(_percentile(vals, 95), 1))
        p99_vals.append(round(_percentile(vals, 99), 1))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=agents, y=p50_vals, name="p50 (median)",
        marker=dict(color="#87D7AF", line=dict(color="#5FAF87", width=1)),
        hovertemplate="<b>%{x}</b><br>p50: %{y}ms<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=agents, y=p95_vals, name="p95",
        marker=dict(color="#5FAF87", line=dict(color="#48D1CC", width=1)),
        hovertemplate="<b>%{x}</b><br>p95: %{y}ms<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=agents, y=p99_vals, name="p99 (tail)",
        marker=dict(color="#F1FA8C", line=dict(color="#E5E500", width=1)),
        hovertemplate="<b>%{x}</b><br>p99: %{y}ms<extra></extra>",
    ))

    fig.update_layout(
        title={"text": "Delegation Latency Percentiles by Agent", "font": {"size": 20, "color": "#87D7AF"}},
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        xaxis=dict(title="Agent", showgrid=False, linecolor="#5FAF87", tickangle=-45),
        yaxis=dict(title="Latency (ms)", showgrid=True, gridcolor="#1a1a1a", linecolor="#5FAF87"),
        barmode="group",
        bargap=0.15,
        bargroupgap=0.1,
        height=400,
        margin=dict(l=60, r=50, t=80, b=120),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0.5)", bordercolor="#5FAF87", borderwidth=1,
        ),
        hoverlabel=dict(bgcolor="#000000", font_size=12, font_family="monospace", bordercolor="#5FAF87"),
    )

    st.plotly_chart(fig, use_container_width=True)
