"""Delegation Analytics Charts.

Cross-run charts built from the delegation JSONL log. All charts are
read-only and fall back gracefully to mock data when no real log exists.
Uses the Matrix Green color theme (#5FAF87, #87D7AF) consistent with
all other analytics components.
"""

import streamlit as st
import plotly.graph_objects as go
from typing import List, Optional
from lib.delegation_parser import DelegationParser, DelegationNode, RunSummary

# Matrix Green theme palette (matches rest of analytics UI)
_GREEN_PRIMARY = "#5FAF87"
_GREEN_LIGHT = "#87D7AF"
_RED = "#FF5555"
_YELLOW = "#F1FA8C"
_BG = "#000000"
_GRID = "#1a1a1a"

_PLOTLY_LAYOUT = dict(
    paper_bgcolor=_BG,
    plot_bgcolor=_BG,
    font=dict(color=_GREEN_PRIMARY),
    xaxis=dict(gridcolor=_GRID, zerolinecolor=_GRID),
    yaxis=dict(gridcolor=_GRID, zerolinecolor=_GRID),
    margin=dict(l=40, r=20, t=40, b=40),
)


def _collect_all_nodes(parser: DelegationParser, run_id: Optional[str] = None) -> List[DelegationNode]:
    """Return a flat list of all delegation nodes, optionally filtered by run."""
    roots = parser.parse_delegation_tree(run_id)
    if not roots:
        roots = parser.get_mock_tree()
    nodes: List[DelegationNode] = []

    def _walk(node: DelegationNode) -> None:
        nodes.append(node)
        for child in node.children:
            _walk(child)

    for root in roots:
        _walk(root)
    return nodes


def render_cost_by_run() -> None:
    """Bar chart — total delegation cost per run, sorted newest-first."""
    st.markdown("#### Cost per Run")
    parser = DelegationParser()
    runs = parser.list_runs()

    if not runs:
        st.caption("No run data available — showing mock example")
        # Synthetic example so the chart is never blank
        labels = ["run-aaa1 (mock)", "run-bbb2 (mock)", "run-ccc3 (mock)"]
        values = [0.0042, 0.0115, 0.0031]
    else:
        labels = []
        values = []
        for run in reversed(runs):  # oldest → newest left-to-right
            nodes = _collect_all_nodes(parser, run.run_id)
            total_cost = sum(n.cost_usd for n in nodes if n.cost_usd is not None)
            labels.append(run.label[:30] + "…" if len(run.label) > 30 else run.label)
            values.append(round(total_cost, 6))

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=_GREEN_PRIMARY,
            hovertemplate="%{x}<br>Cost: $%{y:.4f}<extra></extra>",
        )
    )
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title="Delegation Cost per Run",
        xaxis_title="Run",
        yaxis_title="Total Cost (USD)",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_tokens_by_model() -> None:
    """Horizontal bar chart — cumulative tokens broken down by model."""
    st.markdown("#### Tokens by Model")
    parser = DelegationParser()
    nodes = _collect_all_nodes(parser)

    # Aggregate tokens per model
    model_tokens: dict = {}
    for node in nodes:
        if node.tokens_used is not None:
            model_tokens[node.model] = model_tokens.get(node.model, 0) + node.tokens_used

    if not model_tokens:
        st.caption("No token data available — showing mock example")
        model_tokens = {
            "claude-sonnet-4": 6200,
            "claude-haiku-4": 1400,
        }

    sorted_models = sorted(model_tokens.items(), key=lambda x: x[1])
    models = [m for m, _ in sorted_models]
    tokens = [t for _, t in sorted_models]

    fig = go.Figure(
        go.Bar(
            x=tokens,
            y=models,
            orientation="h",
            marker_color=_GREEN_LIGHT,
            hovertemplate="%{y}<br>Tokens: %{x:,}<extra></extra>",
        )
    )
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title="Token Usage by Model",
        xaxis_title="Total Tokens",
        yaxis_title="Model",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_depth_distribution() -> None:
    """Bar chart — number of delegations at each depth level."""
    st.markdown("#### Delegation Depth Distribution")
    parser = DelegationParser()
    nodes = _collect_all_nodes(parser)
    completed = [n for n in nodes if n.is_complete]

    if not completed:
        st.caption("No delegation data available — showing mock example")
        depth_counts = {0: 1, 1: 2, 2: 2}
    else:
        depth_counts: dict = {}
        for node in completed:
            depth_counts[node.depth] = depth_counts.get(node.depth, 0) + 1

    depths = sorted(depth_counts.keys())
    counts = [depth_counts[d] for d in depths]

    colors = [_GREEN_PRIMARY if d == 0 else _GREEN_LIGHT for d in depths]

    fig = go.Figure(
        go.Bar(
            x=[f"Depth {d}" for d in depths],
            y=counts,
            marker_color=colors,
            hovertemplate="Depth %{x}<br>Count: %{y}<extra></extra>",
        )
    )
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title="Delegations per Depth Level",
        xaxis_title="Depth",
        yaxis_title="Count",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_success_rate_by_depth() -> None:
    """Grouped bar chart — success vs failure count at each depth."""
    st.markdown("#### Success vs Failure by Depth")
    parser = DelegationParser()
    nodes = _collect_all_nodes(parser)
    completed = [n for n in nodes if n.is_complete]

    if not completed:
        st.caption("No delegation data available — showing mock example")
        depths = [0, 1, 2]
        successes = [1, 2, 1]
        failures = [0, 0, 1]
    else:
        depth_success: dict = {}
        depth_failure: dict = {}
        for node in completed:
            d = node.depth
            if node.success:
                depth_success[d] = depth_success.get(d, 0) + 1
            else:
                depth_failure[d] = depth_failure.get(d, 0) + 1
        all_depths = sorted(set(list(depth_success.keys()) + list(depth_failure.keys())))
        depths = all_depths
        successes = [depth_success.get(d, 0) for d in all_depths]
        failures = [depth_failure.get(d, 0) for d in all_depths]

    depth_labels = [f"Depth {d}" for d in depths]

    fig = go.Figure([
        go.Bar(name="Success", x=depth_labels, y=successes, marker_color=_GREEN_PRIMARY),
        go.Bar(name="Failed", x=depth_labels, y=failures, marker_color=_RED),
    ])
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        barmode="group",
        title="Delegation Outcomes by Depth",
        xaxis_title="Depth",
        yaxis_title="Count",
        legend=dict(font=dict(color=_GREEN_PRIMARY)),
    )
    st.plotly_chart(fig, use_container_width=True)
