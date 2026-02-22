"""Delegation Analytics Charts.

Cross-run charts built from the delegation JSONL log. All charts are
read-only and fall back gracefully to mock data when no real log exists.
Uses the Matrix Green color theme (#5FAF87, #87D7AF) consistent with
all other analytics components.
"""

import json
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


def _prune_runs(log_path: str, keep: int) -> tuple:
    """Remove old runs from the JSONL log, keeping the `keep` most recent.

    Reads every line, groups events by run_id, sorts runs newest-first
    by earliest timestamp, then atomically rewrites the file retaining
    only the `keep` most recent runs.  Events with no run_id are preserved.

    Returns (pruned_run_count, removed_event_count, kept_event_count).
    Returns (0, 0, 0) when the file does not exist or is empty.
    """
    if not os.path.exists(log_path):
        return 0, 0, 0

    events = []
    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    if not events:
        return 0, 0, 0

    # Determine first-seen timestamp per run_id (ISO-8601 strings compare correctly).
    run_first_ts: dict = {}
    for ev in events:
        rid = ev.get("run_id")
        if not rid:
            continue
        ts = ev.get("timestamp", "")
        if ts and (rid not in run_first_ts or ts < run_first_ts[rid]):
            run_first_ts[rid] = ts

    # Sort newest-first (descending ISO timestamp).
    sorted_runs = sorted(run_first_ts.keys(), key=lambda r: run_first_ts[r], reverse=True)
    total_runs = len(sorted_runs)

    if total_runs <= keep:
        return 0, 0, len(events)

    prune_ids = set(sorted_runs[keep:])
    kept = [e for e in events if e.get("run_id", "") not in prune_ids]
    removed = len(events) - len(kept)

    # Atomic write: write to .tmp sibling, then rename over original.
    tmp_path = log_path + ".tmp"
    with open(tmp_path, "w") as f:
        for ev in kept:
            f.write(json.dumps(ev) + "\n")
    os.replace(tmp_path, log_path)

    return len(prune_ids), removed, len(kept)


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

        # ── Prune controls (mirrors zeroclaw delegations prune) ──────────────
        st.divider()
        prune_col1, prune_col2, prune_col3 = st.columns([2, 1, 2])
        with prune_col1:
            prune_keep = int(st.number_input(
                "Keep most recent runs",
                min_value=0,
                max_value=9999,
                value=20,
                step=1,
                key="log_health_prune_keep",
                help="Number of most-recent runs to retain; all older runs will be removed",
            ))
        with prune_col2:
            to_remove = max(0, run_count - prune_keep)
            if to_remove > 0:
                st.caption(f"Removes **{to_remove}** old run(s)")
            else:
                st.caption("Nothing to prune")
        with prune_col3:
            if st.button(
                "🗑 Prune old runs",
                key="log_health_prune_btn",
                disabled=(to_remove == 0),
                help=f"Remove {to_remove} old run(s), keeping {prune_keep} most recent",
            ):
                pruned, removed_ev, kept_ev = _prune_runs(log_path, prune_keep)
                if pruned > 0:
                    st.success(
                        f"Pruned {pruned} run(s) ({removed_ev} event(s) removed). "
                        f"{prune_keep} run(s) / {kept_ev} event(s) remaining."
                    )
                    st.rerun()
                else:
                    st.info("Nothing to prune.")


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


def render_model_stats_table(run_id: Optional[str] = None) -> None:
    """Sortable per-model statistics table.

    Mirrors ``zeroclaw delegations models [--run <id>]`` as an interactive
    Streamlit dataframe. When ``run_id`` is set the table is scoped to that
    run; otherwise it aggregates all stored runs.

    Columns: Model | Delegations | Ended | Success % | Total Tokens | Total Cost ($)

    Falls back to a synthetic mock example when no log data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Model Stats {scope}")

    parser = DelegationParser()
    nodes = _collect_all_nodes(parser, run_id)

    if not nodes:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {"Model": "claude-sonnet-4", "Delegations": 4, "Ended": 4,
             "Success %": 100.0, "Total Tokens": 5200, "Total Cost ($)": 0.0184},
            {"Model": "claude-haiku-4", "Delegations": 2, "Ended": 2,
             "Success %": 100.0, "Total Tokens": 1240, "Total Cost ($)": 0.0022},
        ]
        df = pd.DataFrame(rows)
    else:
        agg: dict = {}
        for node in nodes:
            model = node.model or "?"
            if model not in agg:
                agg[model] = {
                    "delegation_count": 0,
                    "end_count": 0,
                    "success_count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            s = agg[model]
            s["delegation_count"] += 1
            if node.is_complete:
                s["end_count"] += 1
                if node.success:
                    s["success_count"] += 1
            if node.tokens_used is not None:
                s["total_tokens"] += node.tokens_used
            if node.cost_usd is not None:
                s["total_cost"] += node.cost_usd

        rows = []
        for model, s in agg.items():
            success_pct = (
                round(100.0 * s["success_count"] / s["end_count"], 1)
                if s["end_count"] > 0
                else None
            )
            rows.append({
                "Model": model,
                "Delegations": s["delegation_count"],
                "Ended": s["end_count"],
                "Success %": success_pct,
                "Total Tokens": s["total_tokens"],
                "Total Cost ($)": round(s["total_cost"], 6),
            })

        # Sort by Total Tokens descending
        rows.sort(key=lambda r: r["Total Tokens"], reverse=True)
        df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Model": st.column_config.TextColumn("Model", width="medium"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ended": st.column_config.NumberColumn("Ended", format="%d"),
            "Success %": st.column_config.NumberColumn("Success %", format="%.1f%%"),
            "Total Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Total Cost ($)": st.column_config.NumberColumn("Cost ($)", format="$%.4f"),
        },
    )


def render_providers_stats_table(run_id: Optional[str] = None) -> None:
    """Sortable per-provider statistics table.

    Mirrors ``zeroclaw delegations providers [--run <id>]`` as an interactive
    Streamlit dataframe. When ``run_id`` is set the table is scoped to that
    run; otherwise it aggregates all stored runs.

    Columns: Provider | Delegations | Ended | Success % | Total Tokens | Total Cost ($)

    Falls back to a synthetic mock example when no log data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Provider Stats {scope}")

    parser = DelegationParser()
    nodes = _collect_all_nodes(parser, run_id)

    if not nodes:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {"Provider": "anthropic", "Delegations": 6, "Ended": 6,
             "Success %": 100.0, "Total Tokens": 6440, "Total Cost ($)": 0.0206},
            {"Provider": "openai", "Delegations": 1, "Ended": 1,
             "Success %": 100.0, "Total Tokens": 820, "Total Cost ($)": 0.0031},
        ]
        df = pd.DataFrame(rows)
    else:
        agg: dict = {}
        for node in nodes:
            provider = node.provider or "?"
            if provider not in agg:
                agg[provider] = {
                    "delegation_count": 0,
                    "end_count": 0,
                    "success_count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            s = agg[provider]
            s["delegation_count"] += 1
            if node.is_complete:
                s["end_count"] += 1
                if node.success:
                    s["success_count"] += 1
            if node.tokens_used is not None:
                s["total_tokens"] += node.tokens_used
            if node.cost_usd is not None:
                s["total_cost"] += node.cost_usd

        rows = []
        for provider, s in agg.items():
            success_pct = (
                round(100.0 * s["success_count"] / s["end_count"], 1)
                if s["end_count"] > 0
                else None
            )
            rows.append({
                "Provider": provider,
                "Delegations": s["delegation_count"],
                "Ended": s["end_count"],
                "Success %": success_pct,
                "Total Tokens": s["total_tokens"],
                "Total Cost ($)": round(s["total_cost"], 6),
            })

        # Sort by Total Tokens descending
        rows.sort(key=lambda r: r["Total Tokens"], reverse=True)
        df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Provider": st.column_config.TextColumn("Provider", width="medium"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ended": st.column_config.NumberColumn("Ended", format="%d"),
            "Success %": st.column_config.NumberColumn("Success %", format="%.1f%%"),
            "Total Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Total Cost ($)": st.column_config.NumberColumn("Cost ($)", format="$%.4f"),
        },
    )


def render_depth_stats_table(run_id: Optional[str] = None) -> None:
    """Sortable per-depth-level statistics table.

    Mirrors ``zeroclaw delegations depth [--run <id>]`` as an interactive
    Streamlit dataframe. Rows represent nesting levels: depth 0 is the
    root agent, depth 1 its direct sub-agents, and so on. Sorted ascending.

    Columns: Depth | Delegations | Ended | Success % | Total Tokens | Total Cost ($)

    Falls back to a synthetic mock example when no log data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Depth Stats {scope}")

    parser = DelegationParser()
    nodes = _collect_all_nodes(parser, run_id)

    if not nodes:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {"Depth": 0, "Delegations": 1, "Ended": 1,
             "Success %": 100.0, "Total Tokens": 3800, "Total Cost ($)": 0.0134},
            {"Depth": 1, "Delegations": 3, "Ended": 3,
             "Success %": 100.0, "Total Tokens": 2400, "Total Cost ($)": 0.0062},
            {"Depth": 2, "Delegations": 2, "Ended": 2,
             "Success %": 50.0, "Total Tokens": 1060, "Total Cost ($)": 0.0010},
        ]
        df = pd.DataFrame(rows)
    else:
        agg: dict = {}
        for node in nodes:
            d = node.depth
            if d not in agg:
                agg[d] = {
                    "delegation_count": 0,
                    "end_count": 0,
                    "success_count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            s = agg[d]
            s["delegation_count"] += 1
            if node.is_complete:
                s["end_count"] += 1
                if node.success:
                    s["success_count"] += 1
            if node.tokens_used is not None:
                s["total_tokens"] += node.tokens_used
            if node.cost_usd is not None:
                s["total_cost"] += node.cost_usd

        rows = []
        for depth, s in agg.items():
            success_pct = (
                round(100.0 * s["success_count"] / s["end_count"], 1)
                if s["end_count"] > 0
                else None
            )
            rows.append({
                "Depth": depth,
                "Delegations": s["delegation_count"],
                "Ended": s["end_count"],
                "Success %": success_pct,
                "Total Tokens": s["total_tokens"],
                "Total Cost ($)": round(s["total_cost"], 6),
            })

        # Sort by Depth ascending (root first)
        rows.sort(key=lambda r: r["Depth"])
        df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Depth": st.column_config.NumberColumn("Depth", format="%d"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ended": st.column_config.NumberColumn("Ended", format="%d"),
            "Success %": st.column_config.NumberColumn("Success %", format="%.1f%%"),
            "Total Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Total Cost ($)": st.column_config.NumberColumn("Cost ($)", format="$%.4f"),
        },
    )


def render_errors_table(run_id: Optional[str] = None) -> None:
    """Failed-delegation errors table.

    Mirrors ``zeroclaw delegations errors [--run <id>]`` as an interactive
    Streamlit dataframe. Rows represent completed delegations where
    ``success=False``, sorted oldest-first (ascending timestamp). Error
    messages are shown in full (the CLI truncates to 80 chars; the UI can
    afford the extra width).

    Columns: # | Run | Agent | Depth | Duration | Error Message

    Falls back to a synthetic mock example when no failures are found.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Delegation Errors {scope}")

    parser = DelegationParser()
    nodes = _collect_all_nodes(parser, run_id)
    failed = [n for n in nodes if n.is_complete and not n.success]

    if not failed:
        st.caption("No failed delegations — showing mock example")
        rows = [
            {
                "#": 1,
                "Run": "abc12345",
                "Agent": "research",
                "Depth": 1,
                "Duration": "3.21s",
                "Error Message": "Tool call timed out after 30 s — no response from provider",
            },
            {
                "#": 2,
                "Run": "abc12345",
                "Agent": "codebase_analyzer",
                "Depth": 2,
                "Duration": "0.89s",
                "Error Message": "Rate limit exceeded: retry after 60 s",
            },
        ]
        df = pd.DataFrame(rows)
    else:
        def _fmt_ms(ms: Optional[int]) -> str:
            if ms is None:
                return "—"
            return f"{ms}ms" if ms < 1000 else f"{ms / 1000:.2f}s"

        # Sort oldest failure first (mirrors CLI ascending timestamp order)
        failed_sorted = sorted(
            failed,
            key=lambda n: n.start_time if n.start_time is not None else datetime.min,
        )

        rows = []
        for i, node in enumerate(failed_sorted, start=1):
            run_prefix = (node.run_id or "")[:8]
            rows.append({
                "#": i,
                "Run": run_prefix,
                "Agent": node.agent_name,
                "Depth": node.depth,
                "Duration": _fmt_ms(node.duration_ms),
                "Error Message": node.error_message or "—",
            })
        df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Run": st.column_config.TextColumn("Run", width="small"),
            "Agent": st.column_config.TextColumn("Agent", width="medium"),
            "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
            "Duration": st.column_config.TextColumn("Duration", width="small"),
            "Error Message": st.column_config.TextColumn("Error Message"),
        },
    )


def render_slow_table(run_id: Optional[str] = None) -> None:
    """Slowest-delegations table.

    Mirrors ``zeroclaw delegations slow [--run <id>] [--limit N]`` as an
    interactive Streamlit dataframe. Rows represent completed delegations
    (``DelegationEnd`` events with a ``duration_ms`` value), sorted by
    duration descending (slowest first). A number-input lets the user
    control how many rows to display (default: 10, matches CLI default).

    Columns: # | Run | Agent | Depth | Duration (ms) | Tokens | Cost ($)

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Slowest Delegations {scope}")

    limit = int(st.number_input(
        "Show top N slowest",
        min_value=1,
        max_value=200,
        value=10,
        step=1,
        key="slow_table_limit",
        help="Number of slowest delegations to display (mirrors --limit in CLI)",
    ))

    parser = DelegationParser()
    nodes = _collect_all_nodes(parser, run_id)
    timed = [n for n in nodes if n.is_complete and n.duration_ms is not None]

    if not timed:
        st.caption("No timed delegation data — showing mock example")
        rows = [
            {
                "#": 1,
                "Run": "abc12345",
                "Agent": "main",
                "Depth": 0,
                "Duration (ms)": 5234,
                "Tokens": 3800,
                "Cost ($)": 0.0134,
            },
            {
                "#": 2,
                "Run": "abc12345",
                "Agent": "research",
                "Depth": 1,
                "Duration (ms)": 3210,
                "Tokens": 2400,
                "Cost ($)": 0.0062,
            },
        ]
        df = pd.DataFrame(rows[:limit])
    else:
        timed_sorted = sorted(timed, key=lambda n: n.duration_ms, reverse=True)  # type: ignore[arg-type]

        rows = []
        for i, node in enumerate(timed_sorted[:limit], start=1):
            run_prefix = (node.run_id or "")[:8]
            rows.append({
                "#": i,
                "Run": run_prefix,
                "Agent": node.agent_name,
                "Depth": node.depth,
                "Duration (ms)": node.duration_ms,
                "Tokens": node.tokens_used,
                "Cost ($)": round(node.cost_usd, 6) if node.cost_usd is not None else None,
            })
        df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Run": st.column_config.TextColumn("Run", width="small"),
            "Agent": st.column_config.TextColumn("Agent", width="medium"),
            "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
            "Duration (ms)": st.column_config.NumberColumn("Duration (ms)", format="%d"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.NumberColumn("Cost ($)", format="$%.4f"),
        },
    )


def render_cost_breakdown_table(run_id: Optional[str] = None) -> None:
    """Per-run cost breakdown table sorted by total cost descending.

    Mirrors ``zeroclaw delegations cost [--run <id>]`` as an interactive
    Streamlit dataframe. One row per stored run, sorted most-expensive first.
    When ``run_id`` is set, only that run is shown.

    Columns: # | Run | Start | Delegations | Tokens | Cost ($) | Avg/Del ($)

    ``Avg/Del`` is the average cost per completed delegation (total cost
    divided by the number of ``DelegationEnd`` events); shown as ``None``
    when no ends are recorded.

    Falls back to a synthetic mock example when no log data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Cost Breakdown by Run {scope}")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {
                "#": 1,
                "Run": "abc12345",
                "Start": "2026-01-02 11:00:00",
                "Delegations": 7,
                "Tokens": 7260,
                "Cost ($)": 0.0237,
                "Avg/Del ($)": 0.0034,
            },
            {
                "#": 2,
                "Run": "def67890",
                "Start": "2026-01-01 09:30:00",
                "Delegations": 3,
                "Tokens": 2100,
                "Cost ($)": 0.0074,
                "Avg/Del ($)": 0.0025,
            },
        ]
        df = pd.DataFrame(rows)
    else:
        # Aggregate per run_id from raw events.
        agg: dict = {}
        for ev in events:
            rid = ev.get("run_id")
            if not rid:
                continue
            if rid not in agg:
                agg[rid] = {
                    "start_time": None,
                    "delegation_count": 0,
                    "end_count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            s = agg[rid]
            ts_str = ev.get("timestamp")
            if ts_str:
                try:
                    from datetime import timezone
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if s["start_time"] is None or ts < s["start_time"]:
                        s["start_time"] = ts
                except ValueError:
                    pass
            etype = ev.get("event_type")
            if etype == "DelegationStart":
                s["delegation_count"] += 1
            elif etype == "DelegationEnd":
                s["end_count"] += 1
                tok = ev.get("tokens_used")
                if tok is not None:
                    s["total_tokens"] += int(tok)
                cost = ev.get("cost_usd")
                if cost is not None:
                    s["total_cost"] += float(cost)

        # Sort by total cost descending.
        sorted_runs = sorted(
            agg.items(), key=lambda kv: kv[1]["total_cost"], reverse=True
        )

        rows = []
        for i, (rid, s) in enumerate(sorted_runs, start=1):
            start_str = (
                s["start_time"].strftime("%Y-%m-%d %H:%M:%S")
                if s["start_time"] is not None
                else "unknown"
            )
            avg = (
                round(s["total_cost"] / s["end_count"], 6)
                if s["end_count"] > 0 and s["total_cost"] > 0.0
                else None
            )
            rows.append({
                "#": i,
                "Run": rid[:8],
                "Start": start_str,
                "Delegations": s["delegation_count"],
                "Tokens": s["total_tokens"] if s["total_tokens"] > 0 else None,
                "Cost ($)": round(s["total_cost"], 6) if s["total_cost"] > 0.0 else None,
                "Avg/Del ($)": avg,
            })
        df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Run": st.column_config.TextColumn("Run", width="small"),
            "Start": st.column_config.TextColumn("Start"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.NumberColumn("Cost ($)", format="$%.4f"),
            "Avg/Del ($)": st.column_config.NumberColumn("Avg/Del ($)", format="$%.4f"),
        },
    )


def render_recent_table(run_id: Optional[str] = None) -> None:
    """Most-recently-completed delegations table, newest first.

    Mirrors ``zeroclaw delegations recent [--run <id>] [--limit N]`` as an
    interactive Streamlit dataframe. Rows represent completed delegations
    (``DelegationEnd`` events), sorted by finish timestamp descending so the
    most recent delegation appears first. A number-input lets the user control
    how many rows to display (default: 10, matching the CLI default).

    Columns: # | Run | Agent | Depth | Duration | Tokens | Cost ($) | Finished

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Most Recent Delegations {scope}")

    limit = int(st.number_input(
        "Show most recent N",
        min_value=1,
        max_value=200,
        value=10,
        step=1,
        key="recent_table_limit",
        help="Number of most recently completed delegations to display (mirrors --limit in CLI)",
    ))

    parser = DelegationParser()
    nodes = _collect_all_nodes(parser, run_id)
    completed = [n for n in nodes if n.is_complete]

    if not completed:
        st.caption("No completed delegation data — showing mock example")
        rows = [
            {
                "#": 1,
                "Run": "abc12345",
                "Agent": "research",
                "Depth": 1,
                "Duration": "4.51s",
                "Tokens": 2400,
                "Cost ($)": 0.0072,
                "Finished": "2026-02-22 10:30:50",
            },
            {
                "#": 2,
                "Run": "abc12345",
                "Agent": "main",
                "Depth": 0,
                "Duration": "5.23s",
                "Tokens": 3800,
                "Cost ($)": 0.0114,
                "Finished": "2026-02-22 10:30:45",
            },
        ]
        df = pd.DataFrame(rows[:limit])
    else:
        def _fmt_ms(ms: Optional[int]) -> str:
            if ms is None:
                return "—"
            return f"{ms}ms" if ms < 1000 else f"{ms / 1000:.2f}s"

        # Sort newest-finish first; fall back to start_time when end_time is absent.
        completed_sorted = sorted(
            completed,
            key=lambda n: (n.end_time or n.start_time or datetime.min),
            reverse=True,
        )

        rows = []
        for i, node in enumerate(completed_sorted[:limit], start=1):
            run_prefix = (node.run_id or "")[:8]
            finished_str = (
                node.end_time.strftime("%Y-%m-%d %H:%M:%S")
                if node.end_time is not None
                else "—"
            )
            rows.append({
                "#": i,
                "Run": run_prefix,
                "Agent": node.agent_name,
                "Depth": node.depth,
                "Duration": _fmt_ms(node.duration_ms),
                "Tokens": node.tokens_used,
                "Cost ($)": round(node.cost_usd, 6) if node.cost_usd is not None else None,
                "Finished": finished_str,
            })
        df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Run": st.column_config.TextColumn("Run", width="small"),
            "Agent": st.column_config.TextColumn("Agent", width="medium"),
            "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
            "Duration": st.column_config.TextColumn("Duration", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.NumberColumn("Cost ($)", format="$%.4f"),
            "Finished": st.column_config.TextColumn("Finished"),
        },
    )


def render_active_table(run_id: Optional[str] = None) -> None:
    """Currently in-flight delegations table.

    Mirrors ``zeroclaw delegations active [--run <id>]`` as an interactive
    Streamlit dataframe. Shows ``DelegationStart`` events that have no matching
    ``DelegationEnd``, using FIFO matching per (run_id, agent_name, depth) key.
    Rows are sorted oldest-start first so the longest-running delegation appears
    at the top. The elapsed column shows how long each delegation has been
    running based on the current wall-clock time.

    Columns: # | Run | Agent | Depth | Started | Elapsed

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd
    from collections import defaultdict

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Active (In-Flight) Delegations {scope}")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {
                "#": 1,
                "Run": "abc12345",
                "Agent": "research",
                "Depth": 1,
                "Started": "2026-02-22 10:30:00",
                "Elapsed": "12s",
            },
        ]
        df = pd.DataFrame(rows)
    else:
        # FIFO match starts to ends per (run_id, agent_name, depth) key.
        start_queues: dict = defaultdict(list)
        end_counts: dict = defaultdict(int)

        for ev in events:
            etype = ev.get("event_type", "")
            rid = ev.get("run_id", "")
            agent = ev.get("agent_name", "")
            depth = int(ev.get("depth", 0))
            key = (rid, agent, depth)
            if etype == "DelegationStart":
                start_queues[key].append(ev)
            elif etype == "DelegationEnd":
                end_counts[key] += 1

        active: list = []
        for key, starts in start_queues.items():
            matched = end_counts.get(key, 0)
            for start in starts[matched:]:
                active.append(start)

        # Sort oldest-start first.
        active.sort(key=lambda e: e.get("timestamp", ""))

        if not active:
            st.caption("No active (in-flight) delegations found.")
            return

        now = datetime.utcnow()
        rows = []
        for i, ev in enumerate(active, start=1):
            run_prefix = (ev.get("run_id") or "")[:8]
            ts_str = ev.get("timestamp", "")
            started_str = "—"
            elapsed_str = "—"
            if ts_str:
                try:
                    started_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    started_str = started_dt.strftime("%Y-%m-%d %H:%M:%S")
                    secs = int((now - started_dt.replace(tzinfo=None)).total_seconds())
                    secs = max(0, secs)
                    if secs < 60:
                        elapsed_str = f"{secs}s"
                    elif secs < 3600:
                        elapsed_str = f"{secs // 60}m{secs % 60}s"
                    else:
                        elapsed_str = f"{secs // 3600}h{(secs % 3600) // 60}m"
                except ValueError:
                    pass
            rows.append({
                "#": i,
                "Run": run_prefix,
                "Agent": ev.get("agent_name", "?"),
                "Depth": int(ev.get("depth", 0)),
                "Started": started_str,
                "Elapsed": elapsed_str,
            })
        df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Run": st.column_config.TextColumn("Run", width="small"),
            "Agent": st.column_config.TextColumn("Agent", width="medium"),
            "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
            "Started": st.column_config.TextColumn("Started"),
            "Elapsed": st.column_config.TextColumn("Elapsed", width="small"),
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


def render_agent_leaderboard() -> None:
    """Ranked horizontal bar chart — global agent leaderboard by tokens or cost.

    Mirrors ``zeroclaw delegations top --by <metric> --limit <n>``.
    Aggregates across **all** stored runs (not scoped to the shared run
    selector). Two controls let the user choose the ranking metric and the
    number of agents to display.

    Falls back gracefully to mock data when no real log is present.
    """
    st.markdown("#### Agent Leaderboard")

    ctrl_col1, ctrl_col2 = st.columns([2, 1])
    with ctrl_col1:
        rank_by = st.radio(
            "Rank by",
            options=["Tokens", "Cost (USD)"],
            horizontal=True,
            key="leaderboard_rank_by",
            help="Sort agents by cumulative token usage or total cost across all runs",
        )
    with ctrl_col2:
        limit_opt = st.selectbox(
            "Show top",
            options=[5, 10, 20, "All"],
            index=1,  # default: top 10
            key="leaderboard_limit",
            format_func=lambda x: f"Top {x}" if isinstance(x, int) else "All agents",
        )

    parser = DelegationParser()
    nodes = _collect_all_nodes(parser)  # transparent mock fallback when log is absent

    # Aggregate per agent
    agg: dict = {}
    for node in nodes:
        name = node.agent_name
        if name not in agg:
            agg[name] = {"tokens": 0, "cost": 0.0}
        if node.tokens_used is not None:
            agg[name]["tokens"] += node.tokens_used
        if node.cost_usd is not None:
            agg[name]["cost"] += node.cost_usd

    if not agg:
        st.caption("No delegation data available.")
        return

    # Sort by chosen metric, descending
    metric_key = "tokens" if rank_by == "Tokens" else "cost"
    sorted_agents = sorted(agg.items(), key=lambda x: x[1][metric_key], reverse=True)

    # Apply limit
    if isinstance(limit_opt, int):
        sorted_agents = sorted_agents[:limit_opt]

    # Reverse for bottom-up display in horizontal bar chart
    display_agents = [a for a, _ in sorted_agents][::-1]
    display_values = [d[metric_key] for _, d in sorted_agents][::-1]

    if rank_by == "Tokens":
        title = "Agent Leaderboard — Total Tokens (all runs)"
        x_label = "Total Tokens"
        hover = "%{y}<br>Tokens: %{x:,}<extra></extra>"
        bar_color = _GREEN_PRIMARY
    else:
        title = "Agent Leaderboard — Total Cost USD (all runs)"
        x_label = "Total Cost (USD)"
        hover = "%{y}<br>Cost: $%{x:.4f}<extra></extra>"
        bar_color = _GREEN_LIGHT

    chart_height = max(180, len(display_agents) * 32 + 80)
    fig = go.Figure(
        go.Bar(
            x=display_values,
            y=display_agents,
            orientation="h",
            marker_color=bar_color,
            hovertemplate=hover,
        )
    )
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title=title,
        xaxis_title=x_label,
        yaxis_title="Agent",
        height=chart_height,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_run_diff() -> None:
    """Side-by-side run comparison — tokens and cost per agent for two selected runs.

    Mirrors ``zeroclaw delegations diff <run_a> <run_b>`` as a visual chart pair.
    Renders its own independent pair of run selectors (not tied to the shared
    run selector above) so users can compare any two stored runs at any time.

    When fewer than two real runs exist the charts show a synthetic mock example.
    When the same run is selected for both A and B a warning is shown instead.
    """
    st.markdown("#### Run Comparison")

    parser = DelegationParser()
    runs = parser.list_runs()

    # ── Run pair selectors ─────────────────────────────────────────────────
    use_mock = len(runs) < 2

    if use_mock:
        st.caption("Fewer than 2 runs available — showing mock example")
        run_a_id: Optional[str] = None
        run_b_id: Optional[str] = None
        run_a_label = "Run A (mock)"
        run_b_label = "Run B (mock)"
    else:
        options = [r.label for r in runs]
        sel_col1, sel_col2 = st.columns(2)
        with sel_col1:
            label_a = st.selectbox(
                "Baseline (A)",
                options=options,
                index=0,
                key="delegation_diff_run_a",
                help="Baseline run for comparison",
            )
        with sel_col2:
            label_b = st.selectbox(
                "Compare (B)",
                options=options,
                index=min(1, len(options) - 1),
                key="delegation_diff_run_b",
                help="Run to compare against the baseline",
            )
        run_a_id = next((r.run_id for r in runs if r.label == label_a), None)
        run_b_id = next((r.run_id for r in runs if r.label == label_b), None)
        run_a_label = f"A [{run_a_id[:8]}…]" if run_a_id else "A"
        run_b_label = f"B [{run_b_id[:8]}…]" if run_b_id else "B"

        if run_a_id and run_b_id and run_a_id == run_b_id:
            st.warning("Select two different runs to see a meaningful comparison.")
            return

    # ── Collect per-agent aggregates for each run ──────────────────────────
    if use_mock:
        agents     = ["main", "research", "codebase_analyzer", "doc_analyzer"]
        tok_a_vals = [3800, 2400, 800, 600]
        tok_b_vals = [4200, 2800, 700, 900]
        cost_a_vals = [0.0114, 0.0072, 0.0024, 0.0018]
        cost_b_vals = [0.0126, 0.0084, 0.0021, 0.0027]
    else:
        def _agent_agg(rid: Optional[str]) -> dict:
            nodes = []
            real_roots = parser.parse_delegation_tree(rid)
            def _walk(n: DelegationNode) -> None:
                nodes.append(n)
                for c in n.children:
                    _walk(c)
            for root in real_roots:
                _walk(root)
            agg: dict = {}
            for node in nodes:
                name = node.agent_name
                if name not in agg:
                    agg[name] = {"tokens": 0, "cost": 0.0}
                if node.tokens_used is not None:
                    agg[name]["tokens"] += node.tokens_used
                if node.cost_usd is not None:
                    agg[name]["cost"] += node.cost_usd
            return agg

        agg_a = _agent_agg(run_a_id)
        agg_b = _agent_agg(run_b_id)

        all_agents = sorted(
            set(agg_a.keys()) | set(agg_b.keys()),
            key=lambda n: (agg_a.get(n, {}).get("tokens", 0)
                           + agg_b.get(n, {}).get("tokens", 0)),
            reverse=True,
        )
        if not all_agents:
            st.caption("No completed delegation data for the selected runs.")
            return

        agents      = all_agents
        tok_a_vals  = [agg_a.get(n, {}).get("tokens", 0) for n in agents]
        tok_b_vals  = [agg_b.get(n, {}).get("tokens", 0) for n in agents]
        cost_a_vals = [agg_a.get(n, {}).get("cost", 0.0) for n in agents]
        cost_b_vals = [agg_b.get(n, {}).get("cost", 0.0) for n in agents]

    # Reverse for bottom-up display in horizontal bar charts
    agents_rev      = agents[::-1]
    tok_a_rev       = tok_a_vals[::-1]
    tok_b_rev       = tok_b_vals[::-1]
    cost_a_rev      = cost_a_vals[::-1]
    cost_b_rev      = cost_b_vals[::-1]

    # ── Charts ─────────────────────────────────────────────────────────────
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        fig_tok = go.Figure([
            go.Bar(
                name=run_a_label,
                y=agents_rev,
                x=tok_a_rev,
                orientation="h",
                marker_color=_GREEN_PRIMARY,
                hovertemplate="%{y}<br>%{fullData.name}: %{x:,} tokens<extra></extra>",
            ),
            go.Bar(
                name=run_b_label,
                y=agents_rev,
                x=tok_b_rev,
                orientation="h",
                marker_color=_GREEN_LIGHT,
                hovertemplate="%{y}<br>%{fullData.name}: %{x:,} tokens<extra></extra>",
            ),
        ])
        fig_tok.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="group",
            title="Tokens by Agent — A vs B",
            xaxis_title="Tokens",
            yaxis_title="Agent",
            legend=dict(font=dict(color=_GREEN_PRIMARY)),
        )
        st.plotly_chart(fig_tok, use_container_width=True)

    with chart_col2:
        fig_cost = go.Figure([
            go.Bar(
                name=run_a_label,
                y=agents_rev,
                x=cost_a_rev,
                orientation="h",
                marker_color=_GREEN_PRIMARY,
                hovertemplate="%{y}<br>%{fullData.name}: $%{x:.4f}<extra></extra>",
            ),
            go.Bar(
                name=run_b_label,
                y=agents_rev,
                x=cost_b_rev,
                orientation="h",
                marker_color=_GREEN_LIGHT,
                hovertemplate="%{y}<br>%{fullData.name}: $%{x:.4f}<extra></extra>",
            ),
        ])
        fig_cost.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="group",
            title="Cost (USD) by Agent — A vs B",
            xaxis_title="Cost (USD)",
            yaxis_title="Agent",
            legend=dict(font=dict(color=_GREEN_PRIMARY)),
        )
        st.plotly_chart(fig_cost, use_container_width=True)

    # ── Aggregate delta metrics ────────────────────────────────────────────
    total_tok_a  = sum(tok_a_vals)
    total_tok_b  = sum(tok_b_vals)
    total_cost_a = sum(cost_a_vals)
    total_cost_b = sum(cost_b_vals)
    delta_tok    = total_tok_b - total_tok_a
    delta_cost   = total_cost_b - total_cost_a

    def _signed_tok(v: int) -> str:
        return f"+{v:,}" if v > 0 else f"{v:,}"

    def _signed_cost(v: float) -> str:
        if v > 0.000_05:
            return f"+${v:.4f}"
        if v < -0.000_05:
            return f"-${abs(v):.4f}"
        return "$0.0000"

    met_col1, met_col2, met_col3, met_col4 = st.columns(4)
    with met_col1:
        st.metric(f"Total tokens {run_a_label}", f"{total_tok_a:,}" if total_tok_a else "—")
    with met_col2:
        st.metric(f"Total tokens {run_b_label}", f"{total_tok_b:,}" if total_tok_b else "—",
                  delta=_signed_tok(delta_tok) if (total_tok_a or total_tok_b) else None)
    with met_col3:
        st.metric(f"Total cost {run_a_label}", f"${total_cost_a:.4f}" if total_cost_a else "—")
    with met_col4:
        st.metric(f"Total cost {run_b_label}", f"${total_cost_b:.4f}" if total_cost_b else "—",
                  delta=_signed_cost(delta_cost) if (total_cost_a or total_cost_b) else None)


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
