"""Request Volume Chart Component.

Shows agent invocation count over time, derived from real DelegationStart events
in ~/.zeroclaw/state/delegation.jsonl. Displays an honest empty state when no
delegation data is available.
"""

import streamlit as st
import plotly.graph_objects as go
from collections import defaultdict
from datetime import datetime
from lib.delegation_parser import DelegationParser


def render() -> None:
    """Render agent invocation volume chart from real delegation data.

    Reads DelegationStart events from delegation.jsonl, buckets them by date,
    and shows successful vs failed invocation counts over time.
    Falls back to an informative empty state when no data is present.
    """
    parser = DelegationParser()
    events = parser._read_events()

    starts = [e for e in events if e.get("event_type") == "DelegationStart"]
    ends = [e for e in events if e.get("event_type") == "DelegationEnd"]

    if not starts:
        st.info(
            "No delegation data available. "
            "Run ZeroClaw with agent delegation workflows to populate this chart."
        )
        return

    # Build a set of (agent_name, depth, run_id) -> success for end events
    end_success = {}
    for e in ends:
        key = (e.get("agent_name"), e.get("depth"), e.get("run_id"))
        end_success[key] = e.get("success", True)

    # Bucket starts by date, track successful vs failed
    successful_by_date = defaultdict(int)
    failed_by_date = defaultdict(int)

    for s in starts:
        ts_str = s.get("timestamp")
        if not ts_str:
            continue
        ts = parser._parse_timestamp(ts_str)
        if not ts:
            continue
        date_key = ts.strftime("%Y-%m-%d")
        key = (s.get("agent_name"), s.get("depth"), s.get("run_id"))
        if key in end_success and not end_success[key]:
            failed_by_date[date_key] += 1
        else:
            successful_by_date[date_key] += 1

    all_dates = sorted(set(successful_by_date.keys()) | set(failed_by_date.keys()))
    successful_vals = [successful_by_date.get(d, 0) for d in all_dates]
    failed_vals = [failed_by_date.get(d, 0) for d in all_dates]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=all_dates,
        y=successful_vals,
        name="Successful",
        line=dict(color="#5FAF87", width=2),
        mode="lines+markers",
        marker=dict(size=6),
        hovertemplate="<b>Successful</b><br>Date: %{x}<br>Count: %{y}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=all_dates,
        y=failed_vals,
        name="Failed",
        line=dict(color="#FF5555", width=2),
        mode="lines+markers",
        marker=dict(size=6),
        hovertemplate="<b>Failed</b><br>Date: %{x}<br>Count: %{y}<extra></extra>",
    ))

    fig.update_layout(
        title={"text": "Agent Invocations Over Time", "font": {"size": 20, "color": "#87D7AF"}},
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        xaxis=dict(title="Date", showgrid=True, gridcolor="#1a1a1a", linecolor="#5FAF87"),
        yaxis=dict(title="Invocations", showgrid=True, gridcolor="#1a1a1a", linecolor="#5FAF87"),
        height=400,
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0.5)", bordercolor="#5FAF87", borderwidth=1,
        ),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    st.plotly_chart(fig, use_container_width=True)
