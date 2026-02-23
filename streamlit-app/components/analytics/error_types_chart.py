"""Error Types Chart Component.

Shows delegation error breakdown by agent/error message from real
DelegationEnd events. Displays an honest empty state when no error
data exists (ZeroClaw delegations do not use HTTP status codes).
"""

import streamlit as st
import plotly.graph_objects as go
from collections import Counter
from lib.delegation_parser import DelegationParser


def render() -> None:
    """Render delegation error types chart from real data.

    Reads DelegationEnd events where success=false, groups by agent_name
    (and error_message when available), and displays a horizontal bar chart.
    Falls back to an honest empty state when no failures exist.
    """
    parser = DelegationParser()
    events = parser._read_events()

    failures = [
        e for e in events
        if e.get("event_type") == "DelegationEnd" and not e.get("success", True)
    ]

    if not failures:
        st.info(
            "No delegation errors recorded. All delegations completed successfully, "
            "or no delegation data is available yet."
        )
        return

    # Group by agent_name (and error_message snippet if available)
    labels = []
    for f in failures:
        agent = f.get("agent_name", "unknown")
        err = f.get("error_message") or ""
        label = f"{agent}: {err[:60]}" if err else agent
        labels.append(label)

    counts = Counter(labels)
    sorted_items = counts.most_common()
    error_labels = [item[0] for item in sorted_items]
    error_counts = [item[1] for item in sorted_items]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=error_labels,
        x=error_counts,
        orientation="h",
        marker=dict(color="#FF5555", line=dict(color="#000000", width=1)),
        hovertemplate="<b>%{y}</b><br>Count: %{x}<extra></extra>",
        name="Errors",
    ))

    fig.update_layout(
        title={"text": "Delegation Errors by Agent", "font": {"size": 20, "color": "#87D7AF"}, "x": 0.5, "xanchor": "center"},
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF", family="monospace"),
        xaxis=dict(title="Error Count", showgrid=True, gridcolor="#1a1a1a", linecolor="#5FAF87"),
        yaxis=dict(title="", showgrid=False, linecolor="#5FAF87", autorange="reversed"),
        height=400,
        showlegend=False,
        margin=dict(l=200, r=80, t=80, b=50),
        hoverlabel=dict(bgcolor="#000000", font_size=12, font_family="monospace", bordercolor="#FF5555"),
    )

    st.plotly_chart(fig, use_container_width=True)
