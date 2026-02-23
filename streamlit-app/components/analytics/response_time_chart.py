"""Response Time Chart Component.

Shows delegation duration over time, derived from real DelegationEnd events
in ~/.zeroclaw/state/delegation.jsonl. Displays an honest empty state when
no duration data is available.
"""

import streamlit as st
import plotly.graph_objects as go
from lib.delegation_parser import DelegationParser


def render() -> None:
    """Render delegation duration chart from real data.

    Reads DelegationEnd events with duration_ms and plots them over time.
    Falls back to an informative empty state when no data is present.
    """
    parser = DelegationParser()
    events = parser._read_events()

    ends = [
        e for e in events
        if e.get("event_type") == "DelegationEnd" and e.get("duration_ms") is not None
    ]

    if not ends:
        st.info(
            "Duration data not available in current log. "
            "Run ZeroClaw with agent delegation workflows to populate this chart."
        )
        return

    # Sort by timestamp
    def _ts_key(e):
        ts = parser._parse_timestamp(e.get("timestamp"))
        return ts if ts else parser._parse_timestamp("1970-01-01T00:00:00Z")

    ends.sort(key=_ts_key)

    timestamps = []
    durations = []
    agents = []
    for e in ends:
        ts = parser._parse_timestamp(e.get("timestamp"))
        if ts:
            timestamps.append(ts.strftime("%Y-%m-%d %H:%M:%S"))
            durations.append(e["duration_ms"])
            agents.append(e.get("agent_name", "unknown"))

    if not timestamps:
        st.info("Duration data not available in current log format.")
        return

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=timestamps,
        y=durations,
        name="Duration",
        line=dict(color="#5FAF87", width=2),
        mode="lines+markers",
        marker=dict(size=6),
        text=agents,
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Time: %{x}<br>"
            "Duration: %{y}ms<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title={"text": "Delegation Duration Over Time", "font": {"size": 20, "color": "#87D7AF"}},
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        xaxis=dict(title="Time", showgrid=True, gridcolor="#1a1a1a", linecolor="#5FAF87"),
        yaxis=dict(title="Duration (ms)", showgrid=True, gridcolor="#1a1a1a", linecolor="#5FAF87"),
        height=400,
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0.5)", bordercolor="#5FAF87", borderwidth=1,
        ),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    st.plotly_chart(fig, use_container_width=True)
