"""Error Rate Chart Component.

Shows delegation error rate over time, derived from real DelegationEnd events
in ~/.zeroclaw/state/delegation.jsonl. Displays an honest empty state when no
delegation data is available.
"""

import streamlit as st
import plotly.graph_objects as go
from collections import defaultdict
from lib.delegation_parser import DelegationParser


def render() -> None:
    """Render delegation error rate chart from real data.

    Reads DelegationEnd events, computes error rate (success=false / total)
    per date bucket, and charts it over time. Falls back to empty state.
    """
    parser = DelegationParser()
    events = parser._read_events()

    ends = [e for e in events if e.get("event_type") == "DelegationEnd"]

    if not ends:
        st.info(
            "No delegation completion data available. "
            "Run ZeroClaw with agent delegation workflows to populate this chart."
        )
        return

    # Bucket by date
    total_by_date = defaultdict(int)
    failed_by_date = defaultdict(int)

    for e in ends:
        ts = parser._parse_timestamp(e.get("timestamp"))
        if not ts:
            continue
        date_key = ts.strftime("%Y-%m-%d")
        total_by_date[date_key] += 1
        if not e.get("success", True):
            failed_by_date[date_key] += 1

    all_dates = sorted(total_by_date.keys())
    error_rates = []
    for d in all_dates:
        total = total_by_date[d]
        failed = failed_by_date.get(d, 0)
        error_rates.append(round((failed / total) * 100, 1) if total > 0 else 0.0)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=all_dates,
        y=error_rates,
        name="Error Rate",
        line=dict(color="#FF5555", width=2),
        mode="lines+markers",
        marker=dict(size=6),
        hovertemplate="<b>Error Rate</b><br>Date: %{x}<br>Rate: %{y}%<extra></extra>",
    ))

    fig.update_layout(
        title={"text": "Delegation Error Rate Over Time", "font": {"size": 20, "color": "#87D7AF"}},
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        xaxis=dict(title="Date", showgrid=True, gridcolor="#1a1a1a", linecolor="#5FAF87"),
        yaxis=dict(title="Error Rate (%)", showgrid=True, gridcolor="#1a1a1a", linecolor="#5FAF87"),
        height=400,
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0.5)", bordercolor="#5FAF87", borderwidth=1,
        ),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    st.plotly_chart(fig, use_container_width=True)
