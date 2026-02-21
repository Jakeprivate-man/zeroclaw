"""Delegation Analytics Charts.

Cross-run charts built from the delegation JSONL log. All charts are
read-only and fall back gracefully to mock data when no real log exists.
Uses the Matrix Green color theme (#5FAF87, #87D7AF) consistent with
all other analytics components.
"""

import os

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
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


def render_timeline(run_id: Optional[str] = None) -> None:
    """Gantt-style waterfall — each delegation as a horizontal bar on a real timeline.

    Shows start/end times as actual positions so concurrency and duration are
    immediately visible. Defaults to the most recent run when no run_id is given.
    Bars are colored green for success, red for failure, yellow for in-progress.

    Args:
        run_id: Optional run ID to visualize. Defaults to most recent run.
    """
    st.markdown("#### Delegation Timeline")
    parser = DelegationParser()

    # Resolve run_id: default to most recent run
    effective_run_id = run_id
    if effective_run_id is None:
        runs = parser.list_runs()
        if runs:
            effective_run_id = runs[0].run_id  # newest first

    nodes = _collect_all_nodes(parser, effective_run_id)
    timed = [n for n in nodes if n.start_time is not None]

    if not timed:
        st.caption("No timed delegation data available — showing mock example")
        # Synthetic waterfall so the chart is never blank
        now = datetime.now()
        base_ms = now.timestamp() * 1000
        mock_rows = [
            ("main",              0, base_ms,        5234, True,  None),
            ("  research",        1, base_ms + 100,  4512, True,  None),
            ("    codebase_analyzer", 2, base_ms + 200, 1234, True,  None),
            ("    doc_analyzer",  2, base_ms + 1500, 987,  True,  None),
        ]
        labels    = [r[0] for r in mock_rows]
        starts_ms = [r[2] for r in mock_rows]
        durs_ms   = [r[3] for r in mock_rows]
        colors    = [_GREEN_PRIMARY] * len(mock_rows)
        hover_txts = [
            f"<b>{r[0].strip()}</b><br>Depth: {r[1]}<br>Duration: {r[3]}ms<br>Status: ✅ Success"
            for r in mock_rows
        ]
    else:
        timed_sorted = sorted(timed, key=lambda n: (n.start_time, n.depth))
        labels, starts_ms, durs_ms, colors, hover_txts = [], [], [], [], []

        for node in timed_sorted:
            indent = "\u00a0\u00a0" * node.depth   # non-breaking spaces for y-axis indent
            labels.append(f"{indent}{node.agent_name} (d{node.depth})")
            starts_ms.append(node.start_time.timestamp() * 1000)

            if node.duration_ms is not None:
                dur = node.duration_ms
            elif node.end_time:
                dur = int((node.end_time - node.start_time).total_seconds() * 1000)
            else:
                dur = int((datetime.now() - node.start_time).total_seconds() * 1000)
            durs_ms.append(max(dur, 10))  # at least 10ms so the bar is always visible

            if not node.is_complete:
                colors.append(_YELLOW)
            elif node.success:
                colors.append(_GREEN_PRIMARY)
            else:
                colors.append(_RED)

            dur_str = f"{dur}ms" if dur < 1000 else f"{dur / 1000:.2f}s"
            tok_str = f"{node.tokens_used:,}" if node.tokens_used is not None else "—"
            cost_str = f"${node.cost_usd:.4f}" if node.cost_usd is not None else "—"
            hover_txts.append(
                f"<b>{node.agent_name}</b><br>"
                f"Depth: {node.depth}<br>"
                f"Duration: {dur_str}<br>"
                f"Tokens: {tok_str}<br>"
                f"Cost: {cost_str}<br>"
                f"Status: {node.status}"
            )

    row_height_px = 32
    chart_height = max(180, len(labels) * row_height_px + 80)

    fig = go.Figure(
        go.Bar(
            y=labels,
            x=durs_ms,
            base=starts_ms,
            orientation="h",
            marker_color=colors,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_txts,
        )
    )
    fig.update_layout(
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        font=dict(color=_GREEN_PRIMARY),
        title=(
            f"Delegation Timeline [{run_id[:8]}…]"
            if run_id is not None
            else "Delegation Timeline (most recent run)"
            if effective_run_id
            else "Delegation Timeline"
        ),
        margin=dict(l=160, r=20, t=40, b=40),
        height=chart_height,
        xaxis=dict(
            type="date",
            tickformat="%H:%M:%S",
            gridcolor=_GRID,
            zerolinecolor=_GRID,
        ),
        yaxis=dict(
            autorange="reversed",
            gridcolor=_GRID,
            zerolinecolor=_GRID,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_log_health() -> None:
    """Collapsible log health panel: file size, run count, time range, cumulative totals.

    Shows at a glance whether the log file exists, how large it is, how many
    runs are stored, the time range they span, and aggregate token/cost totals.
    Useful after Phase 9 rotation to verify the file is bounded as expected.
    """
    with st.expander("📋 Log Health", expanded=False):
        parser = DelegationParser()
        log_path = parser.log_file

        if not os.path.exists(log_path):
            st.caption(f"Log file not found: `{log_path}`")
            st.info(
                "No delegation events have been recorded yet. "
                "Run ZeroClaw with a workflow that uses the `delegate` tool."
            )
            return

        # File size
        raw_bytes = os.path.getsize(log_path)
        if raw_bytes < 1024:
            size_str = f"{raw_bytes} B"
        elif raw_bytes < 1024 * 1024:
            size_str = f"{raw_bytes / 1024:.1f} KB"
        else:
            size_str = f"{raw_bytes / (1024 * 1024):.2f} MB"

        # Run-level stats
        runs = parser.list_runs()
        run_count = len(runs)
        total_delegations = sum(r.total_delegations for r in runs)

        # Cumulative token/cost from all nodes across all runs
        all_nodes = _collect_all_nodes(parser)
        total_tokens = sum(n.tokens_used for n in all_nodes if n.tokens_used is not None)
        total_cost = sum(n.cost_usd for n in all_nodes if n.cost_usd is not None)
        avg_cost_per_run = total_cost / run_count if run_count > 0 else 0.0

        st.caption(f"Log: `{log_path}`")

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("File size", size_str, help="Size of delegation.jsonl on disk")
        with col2:
            st.metric("Runs stored", run_count,
                      help="Distinct run_id values in the log (bounded by max_runs rotation)")
        with col3:
            st.metric("Delegations", total_delegations,
                      help="Total DelegationStart events across all stored runs")
        with col4:
            st.metric(
                "Total tokens",
                f"{total_tokens:,}" if total_tokens > 0 else "—",
                help="Cumulative tokens across all stored delegation ends",
            )
        with col5:
            st.metric(
                "Total cost",
                f"${total_cost:.4f}" if total_cost > 0 else "—",
                help="Cumulative USD cost across all stored delegation ends",
            )

        if run_count > 0:
            newest = runs[0]
            oldest = runs[-1]
            newest_ts = newest.start_time.strftime("%Y-%m-%d %H:%M") if newest.start_time else "?"
            oldest_ts = oldest.start_time.strftime("%Y-%m-%d %H:%M") if oldest.start_time else "?"
            avg_str = f"${avg_cost_per_run:.4f}" if avg_cost_per_run > 0 else "—"
            st.caption(
                f"Oldest run: {oldest_ts}  \u2022  "
                f"Newest run: {newest_ts}  \u2022  "
                f"Avg cost/run: {avg_str}"
            )


def render_agent_stats_table(run_id: Optional[str] = None) -> None:
    """Sortable per-agent statistics table.

    Mirrors ``zeroclaw delegations stats [--run <id>]`` as an interactive
    Streamlit dataframe. When ``run_id`` is set the table is scoped to that
    run; otherwise it aggregates all stored runs.

    Columns: Agent | Delegations | Ended | Success % | Avg Duration |
             Total Tokens | Total Cost ($)

    Falls back to a synthetic mock example when no log data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    def _fmt_ms(ms: int) -> str:
        return f"{ms}ms" if ms < 1000 else f"{ms / 1000:.2f}s"

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Agent Stats {scope}")

    parser = DelegationParser()
    nodes = _collect_all_nodes(parser, run_id)

    if not nodes:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {"Agent": "main", "Delegations": 3, "Ended": 3, "Success %": 100.0,
             "Avg Duration": "2.50s", "Total Tokens": 3450, "Total Cost ($)": 0.0120},
            {"Agent": "research", "Delegations": 2, "Ended": 2, "Success %": 80.0,
             "Avg Duration": "1.23s", "Total Tokens": 2100, "Total Cost ($)": 0.0074},
            {"Agent": "sub", "Delegations": 1, "Ended": 1, "Success %": 100.0,
             "Avg Duration": "0.50s", "Total Tokens": 890, "Total Cost ($)": 0.0031},
        ]
        df = pd.DataFrame(rows)
    else:
        agg: dict = {}
        for node in nodes:
            name = node.agent_name
            if name not in agg:
                agg[name] = {
                    "delegation_count": 0,
                    "end_count": 0,
                    "success_count": 0,
                    "total_dur_ms": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            s = agg[name]
            s["delegation_count"] += 1
            if node.is_complete:
                s["end_count"] += 1
                if node.success:
                    s["success_count"] += 1
                if node.duration_ms is not None:
                    s["total_dur_ms"] += node.duration_ms
            if node.tokens_used is not None:
                s["total_tokens"] += node.tokens_used
            if node.cost_usd is not None:
                s["total_cost"] += node.cost_usd

        rows = []
        for name, s in agg.items():
            success_pct = (
                round(100.0 * s["success_count"] / s["end_count"], 1)
                if s["end_count"] > 0
                else None
            )
            avg_dur = (
                _fmt_ms(s["total_dur_ms"] // s["end_count"])
                if s["end_count"] > 0
                else "—"
            )
            rows.append({
                "Agent": name,
                "Delegations": s["delegation_count"],
                "Ended": s["end_count"],
                "Success %": success_pct,
                "Avg Duration": avg_dur,
                "Total Tokens": s["total_tokens"] if s["total_tokens"] > 0 else None,
                "Total Cost ($)": s["total_cost"] if s["total_cost"] > 0.0 else None,
            })

        rows.sort(key=lambda r: r["Total Tokens"] or 0, reverse=True)
        df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Agent": st.column_config.TextColumn("Agent", width="medium"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ended": st.column_config.NumberColumn("Ended", format="%d"),
            "Success %": st.column_config.NumberColumn("Success %", format="%.1f%%"),
            "Avg Duration": st.column_config.TextColumn("Avg Duration"),
            "Total Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Total Cost ($)": st.column_config.NumberColumn("Cost ($)", format="$%.4f"),
        },
    )


def render_tokens_by_agent(run_id: Optional[str] = None) -> None:
    """Horizontal bar chart — cumulative tokens broken down by agent name.

    When ``run_id`` is given the chart is scoped to that single run;
    otherwise it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Tokens by Agent {scope}")
    parser = DelegationParser()
    nodes = _collect_all_nodes(parser, run_id)

    agent_tokens: dict = {}
    for node in nodes:
        if node.tokens_used is not None:
            agent_tokens[node.agent_name] = (
                agent_tokens.get(node.agent_name, 0) + node.tokens_used
            )

    if not agent_tokens:
        st.caption("No token data available — showing mock example")
        agent_tokens = {
            "main": 4200,
            "research": 2800,
            "codebase_analyzer": 1100,
            "doc_analyzer": 900,
        }

    sorted_agents = sorted(agent_tokens.items(), key=lambda x: x[1])
    agents = [a for a, _ in sorted_agents]
    tokens = [t for _, t in sorted_agents]

    fig = go.Figure(
        go.Bar(
            x=tokens,
            y=agents,
            orientation="h",
            marker_color=_GREEN_PRIMARY,
            hovertemplate="%{y}<br>Tokens: %{x:,}<extra></extra>",
        )
    )
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title="Token Usage by Agent",
        xaxis_title="Total Tokens",
        yaxis_title="Agent",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_cost_by_agent(run_id: Optional[str] = None) -> None:
    """Horizontal bar chart — cumulative cost broken down by agent name.

    When ``run_id`` is given the chart is scoped to that single run;
    otherwise it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Cost by Agent {scope}")
    parser = DelegationParser()
    nodes = _collect_all_nodes(parser, run_id)

    agent_cost: dict = {}
    for node in nodes:
        if node.cost_usd is not None:
            agent_cost[node.agent_name] = (
                agent_cost.get(node.agent_name, 0.0) + node.cost_usd
            )

    if not agent_cost:
        st.caption("No cost data available — showing mock example")
        agent_cost = {
            "main": 0.0126,
            "research": 0.0084,
            "codebase_analyzer": 0.0033,
            "doc_analyzer": 0.0027,
        }

    sorted_agents = sorted(agent_cost.items(), key=lambda x: x[1])
    agents = [a for a, _ in sorted_agents]
    costs = [round(c, 6) for _, c in sorted_agents]

    fig = go.Figure(
        go.Bar(
            x=costs,
            y=agents,
            orientation="h",
            marker_color=_GREEN_LIGHT,
            hovertemplate="%{y}<br>Cost: $%{x:.4f}<extra></extra>",
        )
    )
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title="Cost by Agent (USD)",
        xaxis_title="Total Cost (USD)",
        yaxis_title="Agent",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_export_buttons(run_id: Optional[str] = None) -> None:
    """CSV and JSONL download buttons for delegation data.

    Provides two ``st.download_button`` widgets side by side — one for CSV
    (columns matching ``zeroclaw delegations export --format csv``), one for
    JSONL (raw event lines straight from the delegation log).

    Only real log data is offered for download; the mock fallback used by
    charts is intentionally excluded. Buttons are disabled when no data is
    available.

    Args:
        run_id: Optional run ID to filter. ``None`` exports all stored runs.
    """
    import io
    import json as _json

    def _csv_field(s: str) -> str:
        """RFC 4180 minimal quoting — matches the Rust CLI implementation."""
        if "," in s or '"' in s or "\n" in s:
            return '"' + s.replace('"', '""') + '"'
        return s

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    suffix = f"_{run_id[:8]}" if run_id is not None else "_all"
    st.markdown(f"#### Export {scope}")

    parser = DelegationParser()

    # Collect real nodes only — do not export synthetic mock data
    real_roots = parser.parse_delegation_tree(run_id)
    real_nodes: List[DelegationNode] = []

    def _walk(node: DelegationNode) -> None:
        real_nodes.append(node)
        for child in node.children:
            _walk(child)

    for root in real_roots:
        _walk(root)

    completed = [n for n in real_nodes if n.is_complete]

    # ── CSV payload ────────────────────────────────────────────────────────
    if completed:
        buf = io.StringIO()
        buf.write(
            "run_id,agent_name,model,depth,duration_ms,"
            "tokens_used,cost_usd,success,timestamp\n"
        )
        for node in completed:
            ts = node.end_time.isoformat() if node.end_time else ""
            row = ",".join([
                _csv_field(node.run_id or ""),
                _csv_field(node.agent_name),
                _csv_field(node.model),
                str(node.depth),
                str(node.duration_ms) if node.duration_ms is not None else "",
                str(node.tokens_used) if node.tokens_used is not None else "",
                f"{node.cost_usd:.6f}" if node.cost_usd is not None else "",
                "true" if node.success else "false",
                _csv_field(ts),
            ])
            buf.write(row + "\n")
        csv_bytes = buf.getvalue().encode()
        csv_disabled = False
    else:
        csv_bytes = (
            "run_id,agent_name,model,depth,duration_ms,"
            "tokens_used,cost_usd,success,timestamp\n"
        ).encode()
        csv_disabled = True

    # ── JSONL payload ──────────────────────────────────────────────────────
    raw_events = parser._read_events(run_id)
    if raw_events:
        jsonl_bytes = ("\n".join(_json.dumps(e) for e in raw_events) + "\n").encode()
        jsonl_disabled = False
    else:
        jsonl_bytes = b""
        jsonl_disabled = True

    # ── Download buttons ───────────────────────────────────────────────────
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.download_button(
            label="⬇ Download CSV",
            data=csv_bytes,
            file_name=f"delegations{suffix}.csv",
            mime="text/csv",
            disabled=csv_disabled,
            help=(
                "Download completed delegation records as CSV, matching "
                "`zeroclaw delegations export --format csv`."
            ),
        )
    with btn_col2:
        st.download_button(
            label="⬇ Download JSONL",
            data=jsonl_bytes,
            file_name=f"delegations{suffix}.jsonl",
            mime="application/x-ndjson",
            disabled=jsonl_disabled,
            help=(
                "Download raw delegation events as JSONL, matching "
                "`zeroclaw delegations export --format jsonl`."
            ),
        )
    if csv_disabled and jsonl_disabled:
        st.caption(
            "No delegation data available — run ZeroClaw to record delegation events."
        )


def render_run_selector() -> Optional[str]:
    """Shared run selector — returns the chosen run_id or None for 'All runs'.

    Renders a compact selectbox that defaults to the most recent run.
    When placed above other delegation components, the returned run_id
    can be threaded through to ``render_timeline``, ``render_delegation_summary``,
    and ``render_delegation_tree`` so all views stay in sync.

    Returns:
        The selected run_id string, or None when 'All runs' is chosen
        or when the log is empty.
    """
    parser = DelegationParser()
    runs = parser.list_runs()
    if not runs:
        return None

    labels = [r.label for r in runs]
    options = ["All runs"] + labels

    selected = st.selectbox(
        "Filter by run",
        options=options,
        index=1 if len(options) > 1 else 0,  # default: most recent run
        key="delegation_shared_run_selector",
        help=(
            "Sync the timeline, summary, and delegation tree to a single "
            "process invocation. 'All runs' shows aggregate cross-run stats "
            "in the summary; the timeline defaults to the most recent run."
        ),
    )

    if selected == "All runs":
        return None

    for run in runs:
        if run.label == selected:
            return run.run_id
    return None
