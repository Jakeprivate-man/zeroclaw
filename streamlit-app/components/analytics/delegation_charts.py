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


def render_agent_history_table(run_id: Optional[str] = None) -> None:
    """Per-agent delegation history table.

    Mirrors ``zeroclaw delegations agent <name> [--run <id>]`` as an
    interactive Streamlit dataframe. The user types an agent name into a
    text input; the table then shows every completed delegation for that
    agent, sorted newest first (timestamp descending).

    Columns: # | Run | Depth | Duration | Tokens | Cost ($) | Ok | Finished

    A caption below the table summarises total occurrences, successes,
    cumulative tokens, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Agent Delegation History {scope}")

    agent_name = st.text_input(
        "Agent name",
        value="",
        key="agent_history_name",
        placeholder="e.g. research",
        help="Exact agent name to filter (case-sensitive). Leave blank to skip.",
    )

    if not agent_name.strip():
        st.caption("Enter an agent name above to view its delegation history.")
        return

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption(f"No delegation data available — showing mock example for {agent_name!r}")
        rows = [
            {
                "#": 1,
                "Run": "abc12345",
                "Depth": 1,
                "Duration": "4512ms",
                "Tokens": 1234,
                "Cost ($)": "$0.0037",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:50",
            },
            {
                "#": 2,
                "Run": "abc12345",
                "Depth": 2,
                "Duration": "2100ms",
                "Tokens": 654,
                "Cost ($)": "$0.0019",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:45",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn("#", format="%d", width="small"),
                "Run": st.column_config.TextColumn("Run", width="small"),
                "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
                "Duration": st.column_config.TextColumn("Duration", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
                "Ok": st.column_config.TextColumn("Ok", width="small"),
                "Finished": st.column_config.TextColumn("Finished"),
            },
        )
        st.caption("2 occurrence(s) — 2 succeeded • 1888 total tokens • $0.0056 total cost (mock)")
        return

    # Filter completed delegations for the named agent.
    agent_events = [
        ev for ev in events
        if ev.get("event_type") == "DelegationEnd"
        and ev.get("agent_name") == agent_name.strip()
    ]

    if not agent_events:
        st.caption(f"No completed delegations found for agent {agent_name!r} in the selected scope.")
        return

    # Sort newest first.
    agent_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    rows = []
    total_tokens = 0
    total_cost = 0.0
    success_count = 0
    for i, ev in enumerate(agent_events, start=1):
        run_prefix = (ev.get("run_id") or "")[:8]
        depth = int(ev.get("depth", 0))
        dur_ms = ev.get("duration_ms")
        dur_str = f"{dur_ms}ms" if dur_ms is not None else "—"
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        ok = ev.get("success", False)
        ok_str = "yes" if ok else "no"
        ts_str = ev.get("timestamp", "")
        finished_str = "—"
        if ts_str:
            try:
                finished_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                finished_str = finished_dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        total_tokens += tokens
        total_cost += cost
        if ok:
            success_count += 1
        rows.append({
            "#": i,
            "Run": run_prefix,
            "Depth": depth,
            "Duration": dur_str,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
            "Ok": ok_str,
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
            "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
            "Duration": st.column_config.TextColumn("Duration", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            "Ok": st.column_config.TextColumn("Ok", width="small"),
            "Finished": st.column_config.TextColumn("Finished"),
        },
    )
    n = len(agent_events)
    st.caption(
        f"{n} occurrence(s) — {success_count} succeeded "
        f"• {total_tokens} total tokens • ${total_cost:.4f} total cost"
    )


def render_model_history_table(run_id: Optional[str] = None) -> None:
    """Per-model delegation history table.

    Mirrors ``zeroclaw delegations model <name> [--run <id>]`` as an
    interactive Streamlit dataframe. The user types a model name into a
    text input; the table then shows every completed delegation for that
    model, sorted newest first (timestamp descending).

    Includes an Agent column (unlike the agent history table) so that
    different agents using the same model are distinguishable at a glance.

    Columns: # | Run | Agent | Depth | Duration | Tokens | Cost ($) | Ok | Finished

    A caption below the table summarises total occurrences, successes,
    cumulative tokens, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Model Delegation History {scope}")

    model_name = st.text_input(
        "Model name",
        value="",
        key="model_history_name",
        placeholder="e.g. claude-sonnet-4",
        help="Exact model name to filter (case-sensitive). Leave blank to skip.",
    )

    if not model_name.strip():
        st.caption("Enter a model name above to view its delegation history.")
        return

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption(f"No delegation data available — showing mock example for {model_name!r}")
        rows = [
            {
                "#": 1,
                "Run": "abc12345",
                "Agent": "research",
                "Depth": 1,
                "Duration": "4512ms",
                "Tokens": 1234,
                "Cost ($)": "$0.0037",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:50",
            },
            {
                "#": 2,
                "Run": "abc12345",
                "Agent": "main",
                "Depth": 0,
                "Duration": "2100ms",
                "Tokens": 654,
                "Cost ($)": "$0.0019",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:45",
            },
        ]
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
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
                "Ok": st.column_config.TextColumn("Ok", width="small"),
                "Finished": st.column_config.TextColumn("Finished"),
            },
        )
        st.caption("2 occurrence(s) — 2 succeeded • 1888 total tokens • $0.0056 total cost (mock)")
        return

    # Filter completed delegations for the named model.
    model_events = [
        ev for ev in events
        if ev.get("event_type") == "DelegationEnd"
        and ev.get("model") == model_name.strip()
    ]

    if not model_events:
        st.caption(f"No completed delegations found for model {model_name!r} in the selected scope.")
        return

    # Sort newest first.
    model_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    rows = []
    total_tokens = 0
    total_cost = 0.0
    success_count = 0
    for i, ev in enumerate(model_events, start=1):
        run_prefix = (ev.get("run_id") or "")[:8]
        agent = ev.get("agent_name", "?")
        depth = int(ev.get("depth", 0))
        dur_ms = ev.get("duration_ms")
        dur_str = f"{dur_ms}ms" if dur_ms is not None else "—"
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        ok = ev.get("success", False)
        ok_str = "yes" if ok else "no"
        ts_str = ev.get("timestamp", "")
        finished_str = "—"
        if ts_str:
            try:
                finished_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                finished_str = finished_dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        total_tokens += tokens
        total_cost += cost
        if ok:
            success_count += 1
        rows.append({
            "#": i,
            "Run": run_prefix,
            "Agent": agent,
            "Depth": depth,
            "Duration": dur_str,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
            "Ok": ok_str,
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
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            "Ok": st.column_config.TextColumn("Ok", width="small"),
            "Finished": st.column_config.TextColumn("Finished"),
        },
    )
    n = len(model_events)
    st.caption(
        f"{n} occurrence(s) — {success_count} succeeded "
        f"• {total_tokens} total tokens • ${total_cost:.4f} total cost"
    )


def render_provider_history_table(run_id: Optional[str] = None) -> None:
    """Per-provider delegation history table.

    Mirrors ``zeroclaw delegations provider <name> [--run <id>]`` as an
    interactive Streamlit dataframe. The user types a provider name into a
    text input; the table shows every completed delegation for that provider,
    sorted newest first (timestamp descending).

    Includes Agent and Model columns so that different agents and models
    running on the same provider are distinguishable at a glance.

    Columns: # | Run | Agent | Model | Depth | Duration | Tokens | Cost ($) | Ok | Finished

    A caption below the table summarises total occurrences, successes,
    cumulative tokens, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Provider Delegation History {scope}")

    provider_name = st.text_input(
        "Provider name",
        value="",
        key="provider_history_name",
        placeholder="e.g. anthropic",
        help="Exact provider name to filter (case-sensitive). Leave blank to skip.",
    )

    if not provider_name.strip():
        st.caption("Enter a provider name above to view its delegation history.")
        return

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption(f"No delegation data available — showing mock example for {provider_name!r}")
        rows = [
            {
                "#": 1,
                "Run": "abc12345",
                "Agent": "research",
                "Model": "claude-sonnet-4",
                "Depth": 1,
                "Duration": "4512ms",
                "Tokens": 1234,
                "Cost ($)": "$0.0037",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:50",
            },
            {
                "#": 2,
                "Run": "abc12345",
                "Agent": "main",
                "Model": "claude-sonnet-4",
                "Depth": 0,
                "Duration": "2100ms",
                "Tokens": 654,
                "Cost ($)": "$0.0019",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:45",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn("#", format="%d", width="small"),
                "Run": st.column_config.TextColumn("Run", width="small"),
                "Agent": st.column_config.TextColumn("Agent", width="medium"),
                "Model": st.column_config.TextColumn("Model", width="medium"),
                "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
                "Duration": st.column_config.TextColumn("Duration", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
                "Ok": st.column_config.TextColumn("Ok", width="small"),
                "Finished": st.column_config.TextColumn("Finished"),
            },
        )
        st.caption("2 occurrence(s) — 2 succeeded • 1888 total tokens • $0.0056 total cost (mock)")
        return

    # Filter completed delegations for the named provider.
    provider_events = [
        ev for ev in events
        if ev.get("event_type") == "DelegationEnd"
        and ev.get("provider") == provider_name.strip()
    ]

    if not provider_events:
        st.caption(
            f"No completed delegations found for provider {provider_name!r} "
            "in the selected scope."
        )
        return

    # Sort newest first.
    provider_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    rows = []
    total_tokens = 0
    total_cost = 0.0
    success_count = 0
    for i, ev in enumerate(provider_events, start=1):
        run_prefix = (ev.get("run_id") or "")[:8]
        agent = ev.get("agent_name", "?")
        model = ev.get("model", "?")
        depth = int(ev.get("depth", 0))
        dur_ms = ev.get("duration_ms")
        dur_str = f"{dur_ms}ms" if dur_ms is not None else "—"
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        ok = ev.get("success", False)
        ok_str = "yes" if ok else "no"
        ts_str = ev.get("timestamp", "")
        finished_str = "—"
        if ts_str:
            try:
                finished_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                finished_str = finished_dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        total_tokens += tokens
        total_cost += cost
        if ok:
            success_count += 1
        rows.append({
            "#": i,
            "Run": run_prefix,
            "Agent": agent,
            "Model": model,
            "Depth": depth,
            "Duration": dur_str,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
            "Ok": ok_str,
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
            "Model": st.column_config.TextColumn("Model", width="medium"),
            "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
            "Duration": st.column_config.TextColumn("Duration", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            "Ok": st.column_config.TextColumn("Ok", width="small"),
            "Finished": st.column_config.TextColumn("Finished"),
        },
    )
    n = len(provider_events)
    st.caption(
        f"{n} occurrence(s) — {success_count} succeeded "
        f"• {total_tokens} total tokens • ${total_cost:.4f} total cost"
    )


def render_run_report_table(run_id: Optional[str] = None) -> None:
    """Full chronological delegation report for a single run.

    Mirrors ``zeroclaw delegations run <id>`` as an interactive Streamlit
    dataframe. When a run is selected in the run selector, all completed
    delegations for that run are shown in chronological order (oldest first,
    no row limit), so the user can trace the sequence of agent invocations.

    Unlike the history tables (agent/model/provider), this table does not
    require a text input — the run is determined by the shared run selector.
    If no run is selected, a prompt is shown instead.

    Columns: # | Agent | Depth | Duration | Tokens | Cost ($) | Ok | Finished

    A caption below the table summarises total completions, successes,
    cumulative tokens, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Run ID to report on. ``None`` shows a "select a run" prompt.
    """
    import pandas as pd

    st.markdown("#### Run Delegation Report")

    if run_id is None:
        st.caption("Select a run from the dropdown above to view its full delegation report.")
        return

    scope_label = f"{run_id[:8]}…" if len(run_id) > 8 else run_id
    st.markdown(f"Run: `{scope_label}`")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption(f"No delegation data available — showing mock example for run {scope_label!r}")
        rows = [
            {
                "#": 1,
                "Agent": "research",
                "Depth": 1,
                "Duration": "3200ms",
                "Tokens": 980,
                "Cost ($)": "$0.0029",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:44",
            },
            {
                "#": 2,
                "Agent": "research",
                "Depth": 1,
                "Duration": "4512ms",
                "Tokens": 1234,
                "Cost ($)": "$0.0037",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:50",
            },
            {
                "#": 3,
                "Agent": "main",
                "Depth": 0,
                "Duration": "2100ms",
                "Tokens": 654,
                "Cost ($)": "$0.0019",
                "Ok": "no",
                "Finished": "2026-02-22 10:30:55",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn("#", format="%d", width="small"),
                "Agent": st.column_config.TextColumn("Agent", width="medium"),
                "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
                "Duration": st.column_config.TextColumn("Duration", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
                "Ok": st.column_config.TextColumn("Ok", width="small"),
                "Finished": st.column_config.TextColumn("Finished"),
            },
        )
        st.caption("3 completed — 2 succeeded • 2868 total tokens • $0.0085 total cost (mock)")
        return

    # Filter completed delegations for this run.
    run_events = [
        ev for ev in events
        if ev.get("event_type") == "DelegationEnd"
    ]

    if not run_events:
        st.caption(f"No completed delegations found for run {scope_label!r}.")
        return

    # Sort oldest first (chronological).
    run_events.sort(key=lambda e: e.get("timestamp", ""))

    rows = []
    total_tokens = 0
    total_cost = 0.0
    success_count = 0
    for i, ev in enumerate(run_events, start=1):
        agent = ev.get("agent_name", "?")
        depth = int(ev.get("depth", 0))
        dur_ms = ev.get("duration_ms")
        dur_str = f"{dur_ms}ms" if dur_ms is not None else "—"
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        ok = ev.get("success", False)
        ok_str = "yes" if ok else "no"
        ts_str = ev.get("timestamp", "")
        finished_str = "—"
        if ts_str:
            try:
                finished_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                finished_str = finished_dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        total_tokens += tokens
        total_cost += cost
        if ok:
            success_count += 1
        rows.append({
            "#": i,
            "Agent": agent,
            "Depth": depth,
            "Duration": dur_str,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
            "Ok": ok_str,
            "Finished": finished_str,
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Agent": st.column_config.TextColumn("Agent", width="medium"),
            "Depth": st.column_config.NumberColumn("Depth", format="%d", width="small"),
            "Duration": st.column_config.TextColumn("Duration", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            "Ok": st.column_config.TextColumn("Ok", width="small"),
            "Finished": st.column_config.TextColumn("Finished"),
        },
    )
    n = len(run_events)
    st.caption(
        f"{n} completed — {success_count} succeeded "
        f"• {total_tokens} total tokens • ${total_cost:.4f} total cost"
    )


def render_depth_view_table(run_id: Optional[str] = None) -> None:
    """Per-depth-level delegation listing table.

    Mirrors ``zeroclaw delegations depth-view <level> [--run <id>]`` as an
    interactive Streamlit dataframe. The user selects a nesting depth via a
    number input; the table shows every completed delegation at that depth,
    sorted newest first (timestamp descending).

    Unlike the agent/model/provider history tables, depth is selected via a
    numeric stepper (minimum 0) rather than a free-text input, since depth is
    always a non-negative integer.

    Columns: # | Run | Agent | Duration | Tokens | Cost ($) | Ok | Finished

    A caption below the table summarises total occurrences, successes,
    cumulative tokens, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Depth-View Delegation History {scope}")

    depth_level = int(
        st.number_input(
            "Depth level",
            min_value=0,
            value=0,
            step=1,
            key="depth_view_level",
            help="Nesting depth to filter (0 = root-level, 1 = sub-delegations, …)",
        )
    )

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption(
            f"No delegation data available — showing mock example for depth {depth_level}"
        )
        rows = [
            {
                "#": 1,
                "Run": "abc12345",
                "Agent": "research",
                "Duration": "3200ms",
                "Tokens": 980,
                "Cost ($)": "$0.0029",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:44",
            },
            {
                "#": 2,
                "Run": "abc12345",
                "Agent": "main",
                "Duration": "2100ms",
                "Tokens": 654,
                "Cost ($)": "$0.0019",
                "Ok": "yes",
                "Finished": "2026-02-22 10:30:55",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn("#", format="%d", width="small"),
                "Run": st.column_config.TextColumn("Run", width="small"),
                "Agent": st.column_config.TextColumn("Agent", width="medium"),
                "Duration": st.column_config.TextColumn("Duration", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
                "Ok": st.column_config.TextColumn("Ok", width="small"),
                "Finished": st.column_config.TextColumn("Finished"),
            },
        )
        st.caption("2 occurrence(s) — 2 succeeded • 1634 total tokens • $0.0048 total cost (mock)")
        return

    # Filter completed delegations at this depth.
    depth_events = [
        ev for ev in events
        if ev.get("event_type") == "DelegationEnd"
        and int(ev.get("depth", -1)) == depth_level
    ]

    if not depth_events:
        st.caption(
            f"No completed delegations found at depth {depth_level} "
            "in the selected scope."
        )
        return

    # Sort newest first.
    depth_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    rows = []
    total_tokens = 0
    total_cost = 0.0
    success_count = 0
    for i, ev in enumerate(depth_events, start=1):
        run_prefix = (ev.get("run_id") or "")[:8]
        agent = ev.get("agent_name", "?")
        dur_ms = ev.get("duration_ms")
        dur_str = f"{dur_ms}ms" if dur_ms is not None else "—"
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        ok = ev.get("success", False)
        ok_str = "yes" if ok else "no"
        ts_str = ev.get("timestamp", "")
        finished_str = "—"
        if ts_str:
            try:
                finished_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                finished_str = finished_dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        total_tokens += tokens
        total_cost += cost
        if ok:
            success_count += 1
        rows.append({
            "#": i,
            "Run": run_prefix,
            "Agent": agent,
            "Duration": dur_str,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
            "Ok": ok_str,
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
            "Duration": st.column_config.TextColumn("Duration", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            "Ok": st.column_config.TextColumn("Ok", width="small"),
            "Finished": st.column_config.TextColumn("Finished"),
        },
    )
    n = len(depth_events)
    st.caption(
        f"{n} occurrence(s) — {success_count} succeeded "
        f"• {total_tokens} total tokens • ${total_cost:.4f} total cost"
    )


def render_daily_breakdown_table(run_id: Optional[str] = None) -> None:
    """Per-calendar-day delegation breakdown table.

    Mirrors ``zeroclaw delegations daily [--run <id>]`` as a Streamlit
    dataframe. Groups all completed delegations by UTC calendar date and
    shows aggregate statistics per day, sorted oldest day first.

    Unlike the filter tables (agent/model/provider/run/depth-view), this is
    an aggregate table: each row represents a full day, not an individual
    delegation. No additional input control is needed — the shared run
    selector already provides scope.

    Columns: Date | Count | Ok% | Tokens | Cost ($)

    A caption below the table summarises total days, total delegations,
    total successes, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Daily Delegation Breakdown {scope}")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {
                "Date": "2026-02-20",
                "Count": 14,
                "Ok%": "92.9%",
                "Tokens": 8_420,
                "Cost ($)": "$0.0252",
            },
            {
                "Date": "2026-02-21",
                "Count": 22,
                "Ok%": "100.0%",
                "Tokens": 13_110,
                "Cost ($)": "$0.0393",
            },
            {
                "Date": "2026-02-22",
                "Count": 9,
                "Ok%": "88.9%",
                "Tokens": 5_340,
                "Cost ($)": "$0.0160",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("Date", width="small"),
                "Count": st.column_config.NumberColumn("Count", format="%d"),
                "Ok%": st.column_config.TextColumn("Ok%", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption("3 day(s) • 45 total delegations • 43 succeeded • $0.0805 total cost (mock)")
        return

    # Collect completed delegations, group by UTC calendar date.
    day_stats: dict[str, list[float, int, float]] = {}
    # day_stats[date_str] = [count, success_count, tokens, cost]
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        ts = ev.get("timestamp", "")
        date_str = ts[:10] if len(ts) >= 10 else "unknown"
        ok = bool(ev.get("success", False))
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        if date_str not in day_stats:
            day_stats[date_str] = [0, 0, 0, 0.0]
        day_stats[date_str][0] += 1
        if ok:
            day_stats[date_str][1] += 1
        day_stats[date_str][2] += tokens
        day_stats[date_str][3] += cost

    if not day_stats:
        st.caption("No completed delegations found in the selected scope.")
        return

    # Sort oldest-first: ISO date strings sort correctly lexicographically.
    sorted_dates = sorted(day_stats.keys())

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    for date_str in sorted_dates:
        count, success_count, tokens, cost = day_stats[date_str]
        ok_pct = f"{100.0 * success_count / count:.1f}%" if count > 0 else "—"
        rows.append({
            "Date": date_str,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Date": st.column_config.TextColumn("Date", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    n_days = len(sorted_dates)
    st.caption(
        f"{n_days} day(s)  •  {total_delegations} total delegations  "
        f"•  {total_success} succeeded  •  ${total_cost:.4f} total cost"
    )


def render_hourly_breakdown_table(run_id: Optional[str] = None) -> None:
    """Per-UTC-hour delegation breakdown table.

    Mirrors ``zeroclaw delegations hourly [--run <id>]`` as a Streamlit
    dataframe. Groups all completed delegations by UTC hour-of-day (00–23)
    and shows aggregate statistics per hour, sorted lowest-hour first.

    The hour key is extracted from characters 11–12 of the ISO-8601 timestamp
    (e.g. the event at ``2026-01-15T14:30:00Z`` contributes to ``14:xx``).
    Events from different dates with the same hour merge into the same bucket,
    revealing peak-activity windows across the entire scope.

    Like :func:`render_daily_breakdown_table`, this is an aggregate table with
    no additional input control — scope comes from the shared run selector.

    Columns: Hour (UTC) | Count | Ok% | Tokens | Cost ($)

    A caption below the table summarises active hours, total delegations,
    total successes, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Hourly Delegation Breakdown {scope}")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {
                "Hour (UTC)": "09:xx",
                "Count": 8,
                "Ok%": "100.0%",
                "Tokens": 4_800,
                "Cost ($)": "$0.0144",
            },
            {
                "Hour (UTC)": "14:xx",
                "Count": 15,
                "Ok%": "93.3%",
                "Tokens": 9_300,
                "Cost ($)": "$0.0279",
            },
            {
                "Hour (UTC)": "21:xx",
                "Count": 6,
                "Ok%": "83.3%",
                "Tokens": 3_540,
                "Cost ($)": "$0.0106",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Hour (UTC)": st.column_config.TextColumn("Hour (UTC)", width="small"),
                "Count": st.column_config.NumberColumn("Count", format="%d"),
                "Ok%": st.column_config.TextColumn("Ok%", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption("3 hour(s) active • 29 total delegations • 27 succeeded • $0.0529 total cost (mock)")
        return

    # Collect completed delegations, group by UTC hour-of-day.
    hour_stats: dict[str, list] = {}
    # hour_stats[hour_str] = [count, success_count, tokens, cost]
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        ts = ev.get("timestamp", "")
        if len(ts) < 13:
            continue
        hour_str = ts[11:13]
        ok = bool(ev.get("success", False))
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        if hour_str not in hour_stats:
            hour_stats[hour_str] = [0, 0, 0, 0.0]
        hour_stats[hour_str][0] += 1
        if ok:
            hour_stats[hour_str][1] += 1
        hour_stats[hour_str][2] += tokens
        hour_stats[hour_str][3] += cost

    if not hour_stats:
        st.caption("No completed delegations found in the selected scope.")
        return

    # Sort lowest-hour first: two-digit strings "00"–"23" sort correctly.
    sorted_hours = sorted(hour_stats.keys())

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    for hour_str in sorted_hours:
        count, success_count, tokens, cost = hour_stats[hour_str]
        ok_pct = f"{100.0 * success_count / count:.1f}%" if count > 0 else "—"
        rows.append({
            "Hour (UTC)": f"{hour_str}:xx",
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Hour (UTC)": st.column_config.TextColumn("Hour (UTC)", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    n_hours = len(sorted_hours)
    st.caption(
        f"{n_hours} hour(s) active  •  {total_delegations} total delegations  "
        f"•  {total_success} succeeded  •  ${total_cost:.4f} total cost"
    )


def render_monthly_breakdown_table(run_id: Optional[str] = None) -> None:
    """Per-calendar-month delegation breakdown table.

    Mirrors ``zeroclaw delegations monthly [--run <id>]`` as a Streamlit
    dataframe. Groups all completed delegations by UTC calendar month
    (YYYY-MM) and shows aggregate statistics per month, sorted oldest
    month first.

    The month key is extracted from the first 7 characters of the ISO-8601
    timestamp (e.g. ``2026-01`` from ``2026-01-15T14:30:00Z``). Lexicographic
    ordering of ``YYYY-MM`` strings is identical to chronological order so no
    additional sort step is required.

    Like the daily and hourly tables, this is an aggregate table with no
    additional input control — scope comes from the shared run selector.

    Columns: Month | Count | Ok% | Tokens | Cost ($)

    A caption below the table summarises total months, total delegations,
    total successes, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Monthly Delegation Breakdown {scope}")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {
                "Month": "2025-12",
                "Count": 31,
                "Ok%": "96.8%",
                "Tokens": 18_600,
                "Cost ($)": "$0.0558",
            },
            {
                "Month": "2026-01",
                "Count": 87,
                "Ok%": "97.7%",
                "Tokens": 52_200,
                "Cost ($)": "$0.1566",
            },
            {
                "Month": "2026-02",
                "Count": 45,
                "Ok%": "100.0%",
                "Tokens": 27_000,
                "Cost ($)": "$0.0810",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Month": st.column_config.TextColumn("Month", width="small"),
                "Count": st.column_config.NumberColumn("Count", format="%d"),
                "Ok%": st.column_config.TextColumn("Ok%", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption("3 month(s) • 163 total delegations • 159 succeeded • $0.2934 total cost (mock)")
        return

    # Collect completed delegations, group by UTC calendar month.
    month_stats: dict[str, list] = {}
    # month_stats[month_str] = [count, success_count, tokens, cost]
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        ts = ev.get("timestamp", "")
        if len(ts) < 7:
            continue
        month_str = ts[:7]
        ok = bool(ev.get("success", False))
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        if month_str not in month_stats:
            month_stats[month_str] = [0, 0, 0, 0.0]
        month_stats[month_str][0] += 1
        if ok:
            month_stats[month_str][1] += 1
        month_stats[month_str][2] += tokens
        month_stats[month_str][3] += cost

    if not month_stats:
        st.caption("No completed delegations found in the selected scope.")
        return

    # Sort oldest-first: YYYY-MM strings sort correctly lexicographically.
    sorted_months = sorted(month_stats.keys())

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    for month_str in sorted_months:
        count, success_count, tokens, cost = month_stats[month_str]
        ok_pct = f"{100.0 * success_count / count:.1f}%" if count > 0 else "—"
        rows.append({
            "Month": month_str,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Month": st.column_config.TextColumn("Month", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    n_months = len(sorted_months)
    st.caption(
        f"{n_months} month(s)  •  {total_delegations} total delegations  "
        f"•  {total_success} succeeded  •  ${total_cost:.4f} total cost"
    )


def render_quarterly_breakdown_table(run_id: Optional[str] = None) -> None:
    """Per-calendar-quarter delegation breakdown table.

    Mirrors ``zeroclaw delegations quarterly [--run <id>]`` as a Streamlit
    dataframe. Groups all completed delegations by UTC calendar quarter
    (YYYY-QN) and shows aggregate statistics per quarter, sorted oldest
    quarter first.

    Quarter boundaries mirror the CLI:
      Jan–Mar → Q1 · Apr–Jun → Q2 · Jul–Sep → Q3 · Oct–Dec → Q4

    The quarter key is derived from the month digits in the ISO-8601
    timestamp (characters 5–6). BTreeMap-style lexicographic ordering of
    ``YYYY-QN`` strings is identical to chronological ordering.

    Like the other time-series tables, this is an aggregate table with no
    additional input control — scope comes from the shared run selector.

    Columns: Quarter | Count | Ok% | Tokens | Cost ($)

    A caption below the table summarises total quarters, total delegations,
    total successes, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Quarterly Delegation Breakdown {scope}")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    _MONTH_TO_QUARTER = {
        "01": "Q1", "02": "Q1", "03": "Q1",
        "04": "Q2", "05": "Q2", "06": "Q2",
        "07": "Q3", "08": "Q3", "09": "Q3",
        "10": "Q4", "11": "Q4", "12": "Q4",
    }

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {
                "Quarter": "2025-Q4",
                "Count": 31,
                "Ok%": "96.8%",
                "Tokens": 18_600,
                "Cost ($)": "$0.0558",
            },
            {
                "Quarter": "2026-Q1",
                "Count": 132,
                "Ok%": "98.5%",
                "Tokens": 79_200,
                "Cost ($)": "$0.2376",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Quarter": st.column_config.TextColumn("Quarter", width="small"),
                "Count": st.column_config.NumberColumn("Count", format="%d"),
                "Ok%": st.column_config.TextColumn("Ok%", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption("2 quarter(s) • 163 total delegations • 159 succeeded • $0.2934 total cost (mock)")
        return

    # Collect completed delegations, group by UTC calendar quarter.
    quarter_stats: dict[str, list] = {}
    # quarter_stats[qkey] = [count, success_count, tokens, cost]
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        ts = ev.get("timestamp", "")
        if len(ts) < 7:
            continue
        month_str = ts[5:7]
        q = _MONTH_TO_QUARTER.get(month_str)
        if q is None:
            continue
        qkey = f"{ts[:4]}-{q}"
        ok = bool(ev.get("success", False))
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        if qkey not in quarter_stats:
            quarter_stats[qkey] = [0, 0, 0, 0.0]
        quarter_stats[qkey][0] += 1
        if ok:
            quarter_stats[qkey][1] += 1
        quarter_stats[qkey][2] += tokens
        quarter_stats[qkey][3] += cost

    if not quarter_stats:
        st.caption("No completed delegations found in the selected scope.")
        return

    # Sort oldest-first: YYYY-QN strings sort correctly lexicographically.
    sorted_quarters = sorted(quarter_stats.keys())

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    for qkey in sorted_quarters:
        count, success_count, tokens, cost = quarter_stats[qkey]
        ok_pct = f"{100.0 * success_count / count:.1f}%" if count > 0 else "—"
        rows.append({
            "Quarter": qkey,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Quarter": st.column_config.TextColumn("Quarter", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    n_quarters = len(sorted_quarters)
    st.caption(
        f"{n_quarters} quarter(s)  •  {total_delegations} total delegations  "
        f"•  {total_success} succeeded  •  ${total_cost:.4f} total cost"
    )


def render_agent_model_table(run_id: Optional[str] = None) -> None:
    """Agent × model cross-product breakdown table, ranked by tokens consumed.

    Mirrors ``zeroclaw delegations agent-model [--run <id>]`` as a Streamlit
    dataframe. Groups all completed delegations by the (agent_name × model)
    cross-product and ranks pairs by total tokens consumed (descending).

    Missing ``agent_name`` or ``model`` fields are substituted with
    ``"unknown"``, matching the CLI behaviour.

    Like the other aggregate tables, this has no additional input control —
    scope comes from the shared run selector.

    Columns: # | Agent | Model | Delegations | Tokens | Cost ($)

    A caption below the table summarises total distinct combinations, total
    delegation count, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Agent \u00d7 Model Breakdown {scope}")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {
                "#": 1,
                "Agent": "researcher",
                "Model": "claude-sonnet-4-6",
                "Delegations": 47,
                "Tokens": 28_200,
                "Cost ($)": "$0.0846",
            },
            {
                "#": 2,
                "Agent": "coder",
                "Model": "claude-opus-4-6",
                "Delegations": 23,
                "Tokens": 18_400,
                "Cost ($)": "$0.0552",
            },
            {
                "#": 3,
                "Agent": "reviewer",
                "Model": "claude-haiku-4-5",
                "Delegations": 15,
                "Tokens": 6_000,
                "Cost ($)": "$0.0060",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn("#", format="%d", width="small"),
                "Agent": st.column_config.TextColumn("Agent"),
                "Model": st.column_config.TextColumn("Model"),
                "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption(
            "3 combination(s)  \u2022  85 total delegations  \u2022  $0.1458 total cost (mock)"
        )
        return

    # Aggregate by (agent × model); value = [count, tokens, cost].
    pair_stats: dict[tuple[str, str], list] = {}
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        agent = ev.get("agent_name") or "unknown"
        model = ev.get("model") or "unknown"
        key = (agent, model)
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        if key not in pair_stats:
            pair_stats[key] = [0, 0, 0.0]
        pair_stats[key][0] += 1
        pair_stats[key][1] += tokens
        pair_stats[key][2] += cost

    if not pair_stats:
        st.caption("No completed delegations found in the selected scope.")
        return

    # Sort by tokens descending, then by (agent, model) alphabetically.
    sorted_pairs = sorted(
        pair_stats.items(),
        key=lambda item: (-item[1][1], item[0][0], item[0][1]),
    )

    rows = []
    total_delegations = 0
    total_cost = 0.0
    for rank, ((agent, model), (count, tokens, cost)) in enumerate(sorted_pairs, start=1):
        rows.append({
            "#": rank,
            "Agent": agent,
            "Model": model,
            "Delegations": count,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_cost += cost

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Agent": st.column_config.TextColumn("Agent"),
            "Model": st.column_config.TextColumn("Model"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    n_combos = len(sorted_pairs)
    st.caption(
        f"{n_combos} combination(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  ${total_cost:.4f} total cost"
    )


def render_provider_model_table(run_id: Optional[str] = None) -> None:
    """Provider × model cross-product breakdown table, ranked by tokens consumed.

    Mirrors ``zeroclaw delegations provider-model [--run <id>]`` as a Streamlit
    dataframe. Groups all completed delegations by the (provider × model)
    cross-product and ranks pairs by total tokens consumed (descending).

    Missing ``provider`` or ``model`` fields are substituted with ``"unknown"``,
    matching the CLI behaviour.

    Like the other aggregate tables, this has no additional input control —
    scope comes from the shared run selector.

    Columns: # | Provider | Model | Delegations | Tokens | Cost ($)

    A caption below the table summarises total distinct combinations, total
    delegation count, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Provider \u00d7 Model Breakdown {scope}")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {
                "#": 1,
                "Provider": "anthropic",
                "Model": "claude-sonnet-4-6",
                "Delegations": 58,
                "Tokens": 34_800,
                "Cost ($)": "$0.1044",
            },
            {
                "#": 2,
                "Provider": "anthropic",
                "Model": "claude-opus-4-6",
                "Delegations": 12,
                "Tokens": 9_600,
                "Cost ($)": "$0.0288",
            },
            {
                "#": 3,
                "Provider": "openai",
                "Model": "gpt-4o",
                "Delegations": 7,
                "Tokens": 4_200,
                "Cost ($)": "$0.0126",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn("#", format="%d", width="small"),
                "Provider": st.column_config.TextColumn("Provider"),
                "Model": st.column_config.TextColumn("Model"),
                "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption(
            "3 combination(s)  \u2022  77 total delegations  \u2022  $0.1458 total cost (mock)"
        )
        return

    # Aggregate by (provider × model); value = [count, tokens, cost].
    pair_stats: dict[tuple[str, str], list] = {}
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        provider = ev.get("provider") or "unknown"
        model = ev.get("model") or "unknown"
        key = (provider, model)
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        if key not in pair_stats:
            pair_stats[key] = [0, 0, 0.0]
        pair_stats[key][0] += 1
        pair_stats[key][1] += tokens
        pair_stats[key][2] += cost

    if not pair_stats:
        st.caption("No completed delegations found in the selected scope.")
        return

    # Sort by tokens descending, then by (provider, model) alphabetically.
    sorted_pairs = sorted(
        pair_stats.items(),
        key=lambda item: (-item[1][1], item[0][0], item[0][1]),
    )

    rows = []
    total_delegations = 0
    total_cost = 0.0
    for rank, ((provider, model), (count, tokens, cost)) in enumerate(sorted_pairs, start=1):
        rows.append({
            "#": rank,
            "Provider": provider,
            "Model": model,
            "Delegations": count,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_cost += cost

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Provider": st.column_config.TextColumn("Provider"),
            "Model": st.column_config.TextColumn("Model"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    n_combos = len(sorted_pairs)
    st.caption(
        f"{n_combos} combination(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  ${total_cost:.4f} total cost"
    )


def render_agent_provider_table(run_id: Optional[str] = None) -> None:
    """Agent × provider cross-product breakdown table, ranked by tokens consumed.

    Mirrors ``zeroclaw delegations agent-provider [--run <id>]`` as a Streamlit
    dataframe. Groups all completed delegations by the (agent_name × provider)
    cross-product and ranks pairs by total tokens consumed (descending).

    Missing ``agent_name`` or ``provider`` fields are substituted with
    ``"unknown"``, matching the CLI behaviour.

    Completes the cross-product triad alongside agent-model and provider-model.

    Columns: # | Agent | Provider | Delegations | Tokens | Cost ($)

    A caption below the table summarises total distinct combinations, total
    delegation count, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Agent \u00d7 Provider Breakdown {scope}")

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {
                "#": 1,
                "Agent": "researcher",
                "Provider": "anthropic",
                "Delegations": 47,
                "Tokens": 28_200,
                "Cost ($)": "$0.0846",
            },
            {
                "#": 2,
                "Agent": "coder",
                "Provider": "anthropic",
                "Delegations": 23,
                "Tokens": 13_800,
                "Cost ($)": "$0.0414",
            },
            {
                "#": 3,
                "Agent": "coder",
                "Provider": "openai",
                "Delegations": 8,
                "Tokens": 4_800,
                "Cost ($)": "$0.0144",
            },
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn("#", format="%d", width="small"),
                "Agent": st.column_config.TextColumn("Agent"),
                "Provider": st.column_config.TextColumn("Provider"),
                "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption(
            "3 combination(s)  \u2022  78 total delegations  \u2022  $0.1404 total cost (mock)"
        )
        return

    # Aggregate by (agent × provider); value = [count, tokens, cost].
    pair_stats: dict[tuple[str, str], list] = {}
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        agent = ev.get("agent_name") or "unknown"
        provider = ev.get("provider") or "unknown"
        key = (agent, provider)
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        if key not in pair_stats:
            pair_stats[key] = [0, 0, 0.0]
        pair_stats[key][0] += 1
        pair_stats[key][1] += tokens
        pair_stats[key][2] += cost

    if not pair_stats:
        st.caption("No completed delegations found in the selected scope.")
        return

    # Sort by tokens descending, then by (agent, provider) alphabetically.
    sorted_pairs = sorted(
        pair_stats.items(),
        key=lambda item: (-item[1][1], item[0][0], item[0][1]),
    )

    rows = []
    total_delegations = 0
    total_cost = 0.0
    for rank, ((agent, provider), (count, tokens, cost)) in enumerate(sorted_pairs, start=1):
        rows.append({
            "#": rank,
            "Agent": agent,
            "Provider": provider,
            "Delegations": count,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_cost += cost

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Agent": st.column_config.TextColumn("Agent"),
            "Provider": st.column_config.TextColumn("Provider"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    n_combos = len(sorted_pairs)
    st.caption(
        f"{n_combos} combination(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  ${total_cost:.4f} total cost"
    )


def render_duration_bucket_table(run_id: Optional[str] = None) -> None:
    """Duration-bucket histogram table — delegations grouped by execution speed.

    Mirrors ``zeroclaw delegations duration-bucket [--run <id>]`` as a
    Streamlit dataframe.  Groups all completed delegations into five
    duration buckets and shows aggregate statistics per bucket, ordered
    fastest-first.  Empty buckets are omitted.

    Bucket boundaries:
      instant  <500 ms
      fast     500 ms – 2 s
      normal   2 s – 10 s
      slow     10 s – 60 s
      very slow  ≥ 60 s

    Columns: Bucket | Count | Ok% | Tokens | Cost ($)

    A caption below summarises populated bucket count, total delegations,
    successes, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}…]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Duration Bucket Breakdown {scope}")

    _BUCKETS = [
        ("<500ms",    0,       499),
        ("500ms–2s",  500,     1_999),
        ("2s–10s",    2_000,   9_999),
        ("10s–60s",   10_000,  59_999),
        (">60s",      60_000,  float("inf")),
    ]

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available — showing mock example")
        rows = [
            {"Bucket": "<500ms",   "Count": 12, "Ok%": "100.0%", "Tokens": 7_200, "Cost ($)": "$0.0216"},
            {"Bucket": "500ms–2s", "Count": 34, "Ok%": "97.1%",  "Tokens": 20_400, "Cost ($)": "$0.0612"},
            {"Bucket": "2s–10s",   "Count": 28, "Ok%": "96.4%",  "Tokens": 16_800, "Cost ($)": "$0.0504"},
            {"Bucket": "10s–60s",  "Count": 9,  "Ok%": "88.9%",  "Tokens": 5_400,  "Cost ($)": "$0.0162"},
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Bucket": st.column_config.TextColumn("Bucket", width="small"),
                "Count": st.column_config.NumberColumn("Count", format="%d"),
                "Ok%": st.column_config.TextColumn("Ok%", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption(
            "4 bucket(s) populated  \u2022  83 total delegations  "
            "\u2022  80 succeeded  \u2022  $0.1494 total cost (mock)"
        )
        return

    # Accumulate per bucket: [count, success_count, tokens, cost]
    bucket_stats = [[0, 0, 0, 0.0] for _ in _BUCKETS]
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        duration_ms = int(ev.get("duration_ms") or 0)
        ok = bool(ev.get("success", False))
        tokens = int(ev.get("tokens_used") or 0)
        cost = float(ev.get("cost_usd") or 0.0)
        for i, (_, lo, hi) in enumerate(_BUCKETS):
            if lo <= duration_ms <= hi:
                bucket_stats[i][0] += 1
                if ok:
                    bucket_stats[i][1] += 1
                bucket_stats[i][2] += tokens
                bucket_stats[i][3] += cost
                break

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    populated = 0
    for (label, _, _), (count, success_count, tokens, cost) in zip(_BUCKETS, bucket_stats):
        if count == 0:
            continue
        populated += 1
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Bucket": label,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Bucket": st.column_config.TextColumn("Bucket", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{populated} bucket(s) populated  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_token_bucket_table(run_id: Optional[str] = None) -> None:
    """Token-bucket histogram table — delegations grouped by tokens consumed.

    Mirrors ``zeroclaw delegations token-bucket [--run <id>]`` as a
    Streamlit dataframe.  Groups all completed delegations into five
    fixed-width token buckets and shows aggregate statistics per bucket,
    ordered smallest-to-largest.  Empty buckets are omitted.

    Bucket boundaries:
      micro    0 – 99 tokens
      small    100 – 999 tokens
      medium   1 000 – 9 999 tokens
      large    10 000 – 99 999 tokens
      xlarge   100 000+ tokens

    Columns: Bucket | Count | Ok% | Tokens | Cost ($)

    A caption below summarises populated bucket count, total delegations,
    successes, and cumulative cost — mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Token Bucket Breakdown {scope}")

    _BUCKETS = [
        ("0\u201399",       0,       99),
        ("100\u2013999",    100,     999),
        ("1k\u20139.9k",    1_000,   9_999),
        ("10k\u201399.9k",  10_000,  99_999),
        ("100k+",           100_000, float("inf")),
    ]

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available \u2014 showing mock example")
        rows = [
            {"Bucket": "100\u2013999",   "Count": 15, "Ok%": "100.0%", "Tokens": 9_000,   "Cost ($)": "$0.0270"},
            {"Bucket": "1k\u20139.9k",   "Count": 34, "Ok%": "97.1%",  "Tokens": 102_000, "Cost ($)": "$0.3060"},
            {"Bucket": "10k\u201399.9k", "Count": 7,  "Ok%": "85.7%",  "Tokens": 73_500,  "Cost ($)": "$0.2940"},
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Bucket": st.column_config.TextColumn("Bucket", width="small"),
                "Count": st.column_config.NumberColumn("Count", format="%d"),
                "Ok%": st.column_config.TextColumn("Ok%", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption(
            "3 bucket(s) populated  \u2022  56 total delegations  "
            "\u2022  53 succeeded  \u2022  $0.6270 total cost (mock)"
        )
        return

    # Accumulate per bucket: [count, success_count, tokens, cost]
    bucket_stats = [[0, 0, 0, 0.0] for _ in _BUCKETS]
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        tokens_used = int(ev.get("tokens_used") or 0)
        ok = bool(ev.get("success", False))
        cost = float(ev.get("cost_usd") or 0.0)
        for i, (_, lo, hi) in enumerate(_BUCKETS):
            if lo <= tokens_used <= hi:
                bucket_stats[i][0] += 1
                if ok:
                    bucket_stats[i][1] += 1
                bucket_stats[i][2] += tokens_used
                bucket_stats[i][3] += cost
                break

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    populated = 0
    for (label, _, _), (count, success_count, tokens, cost) in zip(_BUCKETS, bucket_stats):
        if count == 0:
            continue
        populated += 1
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Bucket": label,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Bucket": st.column_config.TextColumn("Bucket", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{populated} bucket(s) populated  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_cost_bucket_table(run_id: Optional[str] = None) -> None:
    """Cost-bucket histogram table — delegations grouped by cost tier.

    Mirrors ``zeroclaw delegations cost-bucket [--run <id>]`` as a
    Streamlit dataframe.  Groups all completed delegations into five
    fixed-width cost buckets and shows aggregate statistics per bucket,
    ordered cheapest-first.  Empty buckets are omitted.

    Bucket boundaries:
      micro   < $0.001
      small   $0.001 \u2013 $0.01
      medium  $0.01 \u2013 $0.10
      large   $0.10 \u2013 $1.00
      xlarge  \u2265 $1.00

    Columns: Bucket | Count | Ok% | Tokens | Cost ($)

    A caption below summarises populated bucket count, total delegations,
    successes, and cumulative cost \u2014 mirroring the CLI footer line.

    Falls back to a synthetic mock example when no real data is present.

    Args:
        run_id: Optional run ID to filter. ``None`` aggregates all runs.
    """
    import pandas as pd

    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Cost Bucket Breakdown {scope}")

    _BUCKETS = [
        ("<$0.001",           0.0,   0.001),
        ("$0.001\u2013$0.01", 0.001, 0.01),
        ("$0.01\u2013$0.10",  0.01,  0.10),
        ("$0.10\u2013$1.00",  0.10,  1.00),
        ("\u2265$1.00",       1.00,  float("inf")),
    ]

    parser = DelegationParser()
    events = parser._read_events(run_id)

    if not events:
        st.caption("No delegation data available \u2014 showing mock example")
        rows = [
            {"Bucket": "<$0.001",           "Count": 18, "Ok%": "100.0%", "Tokens": 5_400,  "Cost ($)": "$0.0090"},
            {"Bucket": "$0.001\u2013$0.01", "Count": 27, "Ok%": "96.3%",  "Tokens": 54_000, "Cost ($)": "$0.1620"},
            {"Bucket": "$0.01\u2013$0.10",  "Count": 11, "Ok%": "90.9%",  "Tokens": 66_000, "Cost ($)": "$0.5280"},
        ]
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Bucket": st.column_config.TextColumn("Bucket", width="small"),
                "Count": st.column_config.NumberColumn("Count", format="%d"),
                "Ok%": st.column_config.TextColumn("Ok%", width="small"),
                "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
            },
        )
        st.caption(
            "3 bucket(s) populated  \u2022  56 total delegations  "
            "\u2022  54 succeeded  \u2022  $0.6990 total cost (mock)"
        )
        return

    # Accumulate per bucket: [count, success_count, tokens, cost]
    bucket_stats = [[0, 0, 0, 0.0] for _ in _BUCKETS]
    for ev in events:
        if ev.get("event_type") != "DelegationEnd":
            continue
        cost_usd = float(ev.get("cost_usd") or 0.0)
        ok = bool(ev.get("success", False))
        tokens = int(ev.get("tokens_used") or 0)
        for i, (_, lo, hi) in enumerate(_BUCKETS):
            if lo <= cost_usd < hi:
                bucket_stats[i][0] += 1
                if ok:
                    bucket_stats[i][1] += 1
                bucket_stats[i][2] += tokens
                bucket_stats[i][3] += cost_usd
                break

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    populated = 0
    for (label, _, _), (count, success_count, tokens, cost) in zip(_BUCKETS, bucket_stats):
        if count == 0:
            continue
        populated += 1
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Bucket": label,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Bucket": st.column_config.TextColumn("Bucket", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{populated} bucket(s) populated  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_weekday_table(run_id: Optional[str] = None) -> None:
    """Weekday breakdown table — delegations aggregated by day-of-week (Mon–Sun).

    When ``run_id`` is given the table is scoped to that single run;
    otherwise it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    from datetime import datetime

    _DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Delegations by Weekday {scope}")
    parser = DelegationParser()
    events = parser._read_events(run_id)

    # slots[i] = (count, success_count, tokens, cost)  Mon=0 … Sun=6
    slots: list = [(0, 0, 0, 0.0)] * 7

    for ev in events:
        if ev.get("event_type") != "delegation_completed":
            continue
        ts = ev.get("timestamp", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        # Python weekday(): Mon=0, …, Sun=6 — matches ISO order
        idx = dt.weekday()
        count, success_count, tokens, cost = slots[idx]
        count += 1
        outcome = ev.get("outcome", "")
        if outcome == "success":
            success_count += 1
        tokens += int(ev.get("tokens_used", 0) or 0)
        cost += float(ev.get("cost_usd", 0.0) or 0.0)
        slots[idx] = (count, success_count, tokens, cost)

    # --- mock data when no real events are present ---
    if all(s[0] == 0 for s in slots):
        slots = [
            (42, 40, 312_400, 0.8821),   # Mon
            (38, 36, 287_100, 0.7934),   # Tue
            (45, 43, 334_200, 0.9412),   # Wed
            (39, 37, 291_800, 0.8103),   # Thu
            (31, 29, 228_600, 0.6247),   # Fri
            (0, 0, 0, 0.0),              # Sat
            (0, 0, 0, 0.0),             # Sun
        ]

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    active_days = 0

    for idx, label in enumerate(_DAYS):
        count, success_count, tokens, cost = slots[idx]
        if count == 0:
            continue
        active_days += 1
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Day": label,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Day": st.column_config.TextColumn("Day", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{active_days} active day(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_weekly_table(run_id: Optional[str] = None) -> None:
    """Per-ISO-week delegation breakdown table (YYYY-WXX), oldest week first.

    When ``run_id`` is given the table is scoped to that single run;
    otherwise it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    from datetime import datetime, timezone

    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Delegations by ISO Week {scope}")
    parser = DelegationParser()
    events = parser._read_events(run_id)

    # week_map[key] = (count, success_count, tokens, cost)
    week_map: dict = {}

    for ev in events:
        if ev.get("event_type") != "delegation_completed":
            continue
        ts = ev.get("timestamp", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        iso_cal = dt.isocalendar()   # (year, week, weekday)
        key = f"{iso_cal[0]}-W{iso_cal[1]:02d}"
        count, success_count, tokens, cost = week_map.get(key, (0, 0, 0, 0.0))
        count += 1
        if ev.get("outcome") == "success":
            success_count += 1
        tokens += int(ev.get("tokens_used", 0) or 0)
        cost += float(ev.get("cost_usd", 0.0) or 0.0)
        week_map[key] = (count, success_count, tokens, cost)

    # --- mock data when no real events are present ---
    if not week_map:
        week_map = {
            "2026-W06": (38, 36, 284_100, 0.7812),
            "2026-W07": (45, 43, 334_500, 0.9344),
            "2026-W08": (41, 39, 308_200, 0.8621),
        }

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0

    for key in sorted(week_map):
        count, success_count, tokens, cost = week_map[key]
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Week": key,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Week": st.column_config.TextColumn("Week", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{len(rows)} week(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_depth_bucket_table(run_id: Optional[str] = None) -> None:
    """Nesting-depth bucket histogram table (root/sub/deep/deeper/very deep).

    When ``run_id`` is given the table is scoped to that single run;
    otherwise it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    _BUCKETS = [
        ("root (0)", 0, 0),
        ("sub (1)", 1, 1),
        ("deep (2)", 2, 2),
        ("deeper (3)", 3, 3),
        ("very deep (4+)", 4, float("inf")),
    ]

    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Delegations by Depth Bucket {scope}")
    parser = DelegationParser()
    events = parser._read_events(run_id)

    # buckets[i] = (count, success_count, tokens, cost)
    buckets: list = [(0, 0, 0, 0.0)] * len(_BUCKETS)

    for ev in events:
        if ev.get("event_type") != "delegation_completed":
            continue
        depth = int(ev.get("depth", 0) or 0)
        idx = None
        for i, (_, lo, hi) in enumerate(_BUCKETS):
            if lo <= depth <= hi:
                idx = i
                break
        if idx is None:
            idx = len(_BUCKETS) - 1
        count, success_count, tokens, cost = buckets[idx]
        count += 1
        if ev.get("outcome") == "success":
            success_count += 1
        tokens += int(ev.get("tokens_used", 0) or 0)
        cost += float(ev.get("cost_usd", 0.0) or 0.0)
        buckets[idx] = (count, success_count, tokens, cost)

    # --- mock data when no real events are present ---
    if all(b[0] == 0 for b in buckets):
        buckets = [
            (62, 60, 468_200, 1.2943),   # root (0)
            (38, 36, 284_100, 0.7812),   # sub (1)
            (14, 13, 103_500, 0.2841),   # deep (2)
            (0, 0, 0, 0.0),             # deeper (3)
            (0, 0, 0, 0.0),             # very deep (4+)
        ]

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    populated = 0

    for i, (label, _, _) in enumerate(_BUCKETS):
        count, success_count, tokens, cost = buckets[i]
        if count == 0:
            continue
        populated += 1
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Depth": label,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Depth": st.column_config.TextColumn("Depth", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{populated} bucket(s) populated  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_model_tier_table(run_id: Optional[str] = None) -> None:
    """Model-family tier breakdown table (haiku / sonnet / opus / other).

    When ``run_id`` is given the table is scoped to that single run;
    otherwise it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    _TIERS = ["haiku", "sonnet", "opus", "other"]

    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Delegations by Model Tier {scope}")
    parser = DelegationParser()
    events = parser._read_events(run_id)

    # tiers[i] = (count, success_count, tokens, cost)
    tiers: list = [(0, 0, 0, 0.0)] * 4

    for ev in events:
        if ev.get("event_type") != "delegation_completed":
            continue
        model = (ev.get("model") or "").lower()
        if "haiku" in model:
            idx = 0
        elif "sonnet" in model:
            idx = 1
        elif "opus" in model:
            idx = 2
        else:
            idx = 3
        count, success_count, tokens, cost = tiers[idx]
        count += 1
        if ev.get("outcome") == "success":
            success_count += 1
        tokens += int(ev.get("tokens_used", 0) or 0)
        cost += float(ev.get("cost_usd", 0.0) or 0.0)
        tiers[idx] = (count, success_count, tokens, cost)

    # --- mock data when no real events are present ---
    if all(t[0] == 0 for t in tiers):
        tiers = [
            (18, 18, 89_400, 0.1124),    # haiku
            (72, 69, 538_200, 1.4893),   # sonnet
            (24, 22, 198_600, 0.8341),   # opus
            (0, 0, 0, 0.0),             # other
        ]

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    populated = 0

    for i, label in enumerate(_TIERS):
        count, success_count, tokens, cost = tiers[i]
        if count == 0:
            continue
        populated += 1
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Tier": label,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tier": st.column_config.TextColumn("Tier", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{populated} tier(s) populated  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_provider_tier_table(run_id: Optional[str] = None) -> None:
    """Provider tier breakdown table (anthropic / openai / google / other).

    When ``run_id`` is given the table is scoped to that single run;
    otherwise it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    _TIERS = ["anthropic", "openai", "google", "other"]

    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Delegations by Provider Tier {scope}")
    parser = DelegationParser()
    events = parser._read_events(run_id)

    # tiers[i] = (count, success_count, tokens, cost)
    tiers: list = [(0, 0, 0, 0.0)] * 4

    for ev in events:
        if ev.get("event_type") != "delegation_completed":
            continue
        provider = (ev.get("provider") or "").lower()
        if "anthropic" in provider:
            idx = 0
        elif "openai" in provider:
            idx = 1
        elif "google" in provider:
            idx = 2
        else:
            idx = 3
        count, success_count, tokens, cost = tiers[idx]
        count += 1
        if ev.get("outcome") == "success":
            success_count += 1
        tokens += int(ev.get("tokens_used", 0) or 0)
        cost += float(ev.get("cost_usd", 0.0) or 0.0)
        tiers[idx] = (count, success_count, tokens, cost)

    # --- mock data when no real events are present ---
    if all(t[0] == 0 for t in tiers):
        tiers = [
            (48, 46, 362_400, 0.9218),   # anthropic
            (22, 21, 148_600, 0.4431),   # openai
            (8, 7, 54_200, 0.1204),      # google
            (0, 0, 0, 0.0),             # other
        ]

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    populated = 0

    for i, label in enumerate(_TIERS):
        count, success_count, tokens, cost = tiers[i]
        if count == 0:
            continue
        populated += 1
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Tier": label,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tier": st.column_config.TextColumn("Tier", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{populated} tier(s) populated  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_time_of_day_table(run_id: Optional[str] = None) -> None:
    """Time-of-day breakdown table (night / morning / afternoon / evening).

    Buckets delegations by UTC hour into four periods matching the Rust
    ``print_time_of_day`` command.  When ``run_id`` is given the table is
    scoped to that single run; otherwise it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    _PERIODS = [
        ("night (00-05)", 0, 5),
        ("morning (06-11)", 6, 11),
        ("afternoon (12-17)", 12, 17),
        ("evening (18-23)", 18, 23),
    ]

    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Delegations by Time of Day {scope}")
    parser = DelegationParser()
    events = parser._read_events(run_id)

    # buckets[i] = (count, success_count, tokens, cost)
    buckets: list = [(0, 0, 0, 0.0)] * 4

    for ev in events:
        if ev.get("event_type") != "delegation_completed":
            continue
        ts = ev.get("timestamp") or ""
        try:
            from datetime import timezone
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(ts.replace("Z", "+00:00"))
            hour = dt.hour
        except (ValueError, AttributeError):
            continue
        idx = next(
            (i for i, (_, lo, hi) in enumerate(_PERIODS) if lo <= hour <= hi),
            3,
        )
        count, success_count, tokens, cost = buckets[idx]
        count += 1
        if ev.get("outcome") == "success":
            success_count += 1
        tokens += int(ev.get("tokens_used", 0) or 0)
        cost += float(ev.get("cost_usd", 0.0) or 0.0)
        buckets[idx] = (count, success_count, tokens, cost)

    # --- mock data when no real events are present ---
    if all(b[0] == 0 for b in buckets):
        buckets = [
            (12, 11, 84_600, 0.2138),    # night
            (34, 33, 248_200, 0.6714),   # morning
            (41, 39, 312_400, 0.8293),   # afternoon
            (27, 26, 194_800, 0.5021),   # evening
        ]

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    populated = 0

    for i, (label, _, _) in enumerate(_PERIODS):
        count, success_count, tokens, cost = buckets[i]
        if count == 0:
            continue
        populated += 1
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Period": label,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Period": st.column_config.TextColumn("Period", width="medium"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{populated} bucket(s) populated  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_day_of_month_table(run_id: Optional[str] = None) -> None:
    """Day-of-month breakdown table (1–31), sorted numerically.

    Aggregates delegations by calendar day of month derived from the UTC
    timestamp, matching the Rust ``print_day_of_month`` command.  When
    ``run_id`` is given the table is scoped to that single run; otherwise
    it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Delegations by Day of Month {scope}")
    parser = DelegationParser()
    events = parser._read_events(run_id)

    # day_map[day] = (count, success_count, tokens, cost)
    day_map: dict = {}

    for ev in events:
        if ev.get("event_type") != "delegation_completed":
            continue
        ts = ev.get("timestamp") or ""
        try:
            from datetime import timezone
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(ts.replace("Z", "+00:00"))
            day = dt.day
        except (ValueError, AttributeError):
            continue
        count, success_count, tokens, cost = day_map.get(day, (0, 0, 0, 0.0))
        count += 1
        if ev.get("outcome") == "success":
            success_count += 1
        tokens += int(ev.get("tokens_used", 0) or 0)
        cost += float(ev.get("cost_usd", 0.0) or 0.0)
        day_map[day] = (count, success_count, tokens, cost)

    # --- mock data when no real events are present ---
    if not day_map:
        day_map = {
            1: (8, 8, 58_400, 0.1482),
            5: (14, 13, 102_600, 0.2714),
            9: (22, 21, 167_800, 0.4293),
            15: (31, 30, 238_400, 0.6021),
            22: (18, 17, 134_200, 0.3518),
            28: (11, 10, 82_600, 0.2147),
        }

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0

    for day in sorted(day_map):
        count, success_count, tokens, cost = day_map[day]
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Day": day,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Day": st.column_config.NumberColumn("Day", format="%d"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{len(rows)} day(s) active  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_token_efficiency_table(run_id: Optional[str] = None) -> None:
    """Token efficiency breakdown table (cost per 1k tokens).

    Buckets delegations by cost-per-1000-tokens into four tiers matching
    the Rust ``print_token_efficiency`` command.  Delegations with zero
    tokens are skipped.  When ``run_id`` is given the table is scoped to
    that single run; otherwise it aggregates across all stored runs.

    Tiers:
        - very cheap: < $0.002 / 1k tokens
        - cheap: $0.002 – $0.008 / 1k tokens
        - moderate: $0.008 – $0.020 / 1k tokens
        - expensive: > $0.020 / 1k tokens

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    _TIERS = [
        ("very cheap", 0.0, 0.002),
        ("cheap", 0.002, 0.008),
        ("moderate", 0.008, 0.020),
        ("expensive", 0.020, float("inf")),
    ]

    scope = f"[{run_id[:8]}\u2026]" if run_id is not None else "(all runs)"
    st.markdown(f"#### Delegations by Token Efficiency {scope}")
    parser = DelegationParser()
    events = parser._read_events(run_id)

    # tiers[i] = (count, success_count, tokens, cost)
    tiers: list = [(0, 0, 0, 0.0)] * 4

    for ev in events:
        if ev.get("event_type") != "delegation_completed":
            continue
        tokens = int(ev.get("tokens_used", 0) or 0)
        if tokens == 0:
            continue
        cost = float(ev.get("cost_usd", 0.0) or 0.0)
        efficiency = cost / (tokens / 1_000.0)
        idx = next(
            (i for i, (_, lo, hi) in enumerate(_TIERS) if lo <= efficiency < hi),
            3,
        )
        count, success_count, t, c = tiers[idx]
        count += 1
        if ev.get("outcome") == "success":
            success_count += 1
        tiers[idx] = (count, success_count, t + tokens, c + cost)

    # --- mock data when no real events are present ---
    if all(t[0] == 0 for t in tiers):
        tiers = [
            (24, 23, 186_000, 0.1488),   # very cheap  (~$0.0008/1k — haiku-like)
            (58, 56, 438_400, 2.1920),   # cheap        (~$0.005/1k — sonnet-like)
            (22, 20, 168_200, 2.5230),   # moderate     (~$0.015/1k — opus-like)
            (4, 4, 28_600, 0.8294),      # expensive    (high-cost calls)
        ]

    rows = []
    total_delegations = 0
    total_success = 0
    total_cost = 0.0
    populated = 0

    for i, (label, _, _) in enumerate(_TIERS):
        count, success_count, tokens, cost = tiers[i]
        if count == 0:
            continue
        populated += 1
        ok_pct = f"{100.0 * success_count / count:.1f}%"
        rows.append({
            "Tier": label,
            "Count": count,
            "Ok%": ok_pct,
            "Tokens": tokens,
            "Cost ($)": f"${cost:.4f}",
        })
        total_delegations += count
        total_success += success_count
        total_cost += cost

    if not rows:
        st.caption("No completed delegations with token data found in the selected scope.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tier": st.column_config.TextColumn("Tier", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{populated} bucket(s) populated  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_success_breakdown_table(run_id: Optional[str] = None) -> None:
    """Table — delegation outcomes (succeeded vs. failed) with share%, tokens, cost.

    When ``run_id`` is given the table is scoped to that single run;
    otherwise it aggregates across all stored runs.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Success Breakdown")

    _OUTCOMES = ["succeeded", "failed"]
    # buckets[i] = (count, tokens, cost)
    buckets: list[list] = [[0, 0, 0.0], [0, 0, 0.0]]
    total_delegations = 0

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                total_delegations += 1
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                idx = 0 if success else 1
                buckets[idx][0] += 1
                buckets[idx][1] += tokens
                buckets[idx][2] += cost
    else:
        # Mock data: realistic ~92% success rate
        buckets = [[276, 1_840_000, 34.6920], [24, 158_000, 2.9740]]
        total_delegations = 300

    total_cost = sum(b[2] for b in buckets)
    total_success = buckets[0][0]

    rows = []
    populated = 0
    for label, (count, tokens, cost) in zip(_OUTCOMES, buckets):
        if count == 0:
            continue
        populated += 1
        share = 100.0 * count / total_delegations if total_delegations > 0 else 0.0
        rows.append({
            "Outcome": label,
            "Count": count,
            "Share%": f"{share:.1f}%",
            "Tokens": tokens,
            "Cost ($)": f"{cost:.4f}",
        })

    if not rows:
        st.info("No delegation events found.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Outcome": st.column_config.TextColumn("Outcome", width="small"),
            "Count": st.column_config.NumberColumn("Count", format="%d"),
            "Share%": st.column_config.TextColumn("Share%", width="small"),
            "Tokens": st.column_config.NumberColumn("Tokens", format="%d"),
            "Cost ($)": st.column_config.TextColumn("Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{populated} outcome(s) present  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_success} succeeded  \u2022  ${total_cost:.4f} total cost"
    )


def render_agent_cost_rank_table(run_id: Optional[str] = None) -> None:
    """Table — agents ranked by average cost per delegation (most expensive first).

    Answers "which agent type is most expensive per individual invocation?" as
    opposed to token-volume ranking.  Columns: rank, agent, delegations, ok%,
    avg_cost, avg_tokens, total_cost.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Agent Cost Rank")

    # agent → [count, success_count, tokens, cost]
    agent_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                agent = ev.get("agent_name") or "unknown"
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if agent not in agent_map:
                    agent_map[agent] = [0, 0, 0, 0.0]
                agent_map[agent][0] += 1
                if success:
                    agent_map[agent][1] += 1
                agent_map[agent][2] += tokens
                agent_map[agent][3] += cost
    else:
        # Mock data: three agents with different avg costs
        agent_map = {
            "research": [48, 45, 640_000, 12.8800],
            "orchestrator": [120, 117, 800_000, 8.0000],
            "writer": [32, 31, 180_000, 1.4400],
        }

    if not agent_map:
        st.info("No delegation events found.")
        return

    # Sort by avg cost desc
    rows = []
    for agent, (count, ok, tokens, cost) in agent_map.items():
        avg_cost = cost / count if count > 0 else 0.0
        avg_tokens = tokens / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Agent": agent,
            "Delegations": count,
            "Ok%": f"{ok_pct:.1f}%",
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Avg Tokens": round(avg_tokens),
            "Total Cost ($)": f"{cost:.4f}",
        })
    rows.sort(key=lambda r: float(r["Avg Cost ($)"]), reverse=True)
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in agent_map.values())
    total_cost = sum(v[3] for v in agent_map.values())

    df = pd.DataFrame(rows, columns=["#", "Agent", "Delegations", "Ok%", "Avg Cost ($)", "Avg Tokens", "Total Cost ($)"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Agent": st.column_config.TextColumn("Agent"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
            "Total Cost ($)": st.column_config.TextColumn("Total Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{len(rows)} agent(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  ${total_cost:.4f} total cost"
    )


def render_model_cost_rank_table(run_id: Optional[str] = None) -> None:
    """Table — models ranked by average cost per delegation (most expensive first).

    Answers "which model is most expensive per individual invocation?" — distinct
    from total-token ranking or agent-level cost ranking.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Model Cost Rank")

    # model → [count, success_count, tokens, cost]
    model_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                model = ev.get("model") or "unknown"
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if model not in model_map:
                    model_map[model] = [0, 0, 0, 0.0]
                model_map[model][0] += 1
                if success:
                    model_map[model][1] += 1
                model_map[model][2] += tokens
                model_map[model][3] += cost
    else:
        # Mock data: three models with distinct avg costs
        model_map = {
            "claude-opus-4-6":   [18, 17, 270_000, 14.4000],
            "claude-sonnet-4-6": [142, 138, 946_000, 18.9200],
            "claude-haiku-4-5":  [40, 40,  80_000,  0.4800],
        }

    if not model_map:
        st.info("No delegation events found.")
        return

    rows = []
    for model, (count, ok, tokens, cost) in model_map.items():
        avg_cost = cost / count if count > 0 else 0.0
        avg_tokens = tokens / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Model": model,
            "Delegations": count,
            "Ok%": f"{ok_pct:.1f}%",
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Avg Tokens": round(avg_tokens),
            "Total Cost ($)": f"{cost:.4f}",
        })
    rows.sort(key=lambda r: float(r["Avg Cost ($)"]), reverse=True)
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in model_map.values())
    total_cost = sum(v[3] for v in model_map.values())

    df = pd.DataFrame(rows, columns=["#", "Model", "Delegations", "Ok%", "Avg Cost ($)", "Avg Tokens", "Total Cost ($)"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Model": st.column_config.TextColumn("Model"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
            "Total Cost ($)": st.column_config.TextColumn("Total Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{len(rows)} model(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  ${total_cost:.4f} total cost"
    )


def render_provider_cost_rank_table(run_id: Optional[str] = None) -> None:
    """Table — providers ranked by average cost per delegation (most expensive first).

    Answers "which provider is most expensive per individual invocation?" — completes
    the cost-rank trio alongside agent-cost-rank and model-cost-rank.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Provider Cost Rank")

    # provider → [count, success_count, tokens, cost]
    provider_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                provider = ev.get("provider") or "unknown"
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if provider not in provider_map:
                    provider_map[provider] = [0, 0, 0, 0.0]
                provider_map[provider][0] += 1
                if success:
                    provider_map[provider][1] += 1
                provider_map[provider][2] += tokens
                provider_map[provider][3] += cost
    else:
        # Mock data: three providers with distinct avg costs
        provider_map = {
            "anthropic": [160, 155, 1_180_000, 64.0000],
            "openai":    [30,  28,   120_000,   4.5000],
            "google":    [10,  10,    40_000,    0.2000],
        }

    if not provider_map:
        st.info("No delegation events found.")
        return

    rows = []
    for provider, (count, ok, tokens, cost) in provider_map.items():
        avg_cost = cost / count if count > 0 else 0.0
        avg_tokens = tokens / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Provider": provider,
            "Delegations": count,
            "Ok%": f"{ok_pct:.1f}%",
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Avg Tokens": round(avg_tokens),
            "Total Cost ($)": f"{cost:.4f}",
        })
    rows.sort(key=lambda r: float(r["Avg Cost ($)"]), reverse=True)
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in provider_map.values())
    total_cost = sum(v[3] for v in provider_map.values())

    df = pd.DataFrame(rows, columns=["#", "Provider", "Delegations", "Ok%", "Avg Cost ($)", "Avg Tokens", "Total Cost ($)"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Provider": st.column_config.TextColumn("Provider"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
            "Total Cost ($)": st.column_config.TextColumn("Total Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{len(rows)} provider(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  ${total_cost:.4f} total cost"
    )


def render_run_cost_rank_table(run_id: Optional[str] = None) -> None:
    """Table — runs ranked by total cost (most expensive run first).

    Answers "which run burned the most money?" — distinct from agent/model/provider
    cost-rank (per-invocation average) and from agent-level top-volume ranking.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Run Cost Rank")

    # run_id → [count, success_count, tokens, cost]
    run_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                rid = ev.get("run_id") or "unknown"
                if run_id and rid != run_id:
                    continue
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if rid not in run_map:
                    run_map[rid] = [0, 0, 0, 0.0]
                run_map[rid][0] += 1
                if success:
                    run_map[rid][1] += 1
                run_map[rid][2] += tokens
                run_map[rid][3] += cost
    else:
        # Mock data: three runs with distinct total costs
        run_map = {
            "run-alpha": [120, 115, 900_000, 28.5000],
            "run-beta":  [45,  42,  280_000, 12.8000],
            "run-gamma": [35,  35,  100_000,  4.2000],
        }

    if not run_map:
        st.info("No delegation events found.")
        return

    rows = []
    for rid, (count, ok, tokens, cost) in run_map.items():
        avg_cost = cost / count if count > 0 else 0.0
        avg_tokens = tokens / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Run": rid,
            "Delegations": count,
            "Ok%": f"{ok_pct:.1f}%",
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Avg Tokens": round(avg_tokens),
            "Total Cost ($)": f"{cost:.4f}",
        })
    # Sort by total_cost desc, ties by run_id asc
    rows.sort(key=lambda r: (-float(r["Total Cost ($)"]), r["Run"]))
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in run_map.values())
    total_cost = sum(v[3] for v in run_map.values())

    df = pd.DataFrame(rows, columns=["#", "Run", "Delegations", "Ok%", "Avg Cost ($)", "Avg Tokens", "Total Cost ($)"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Run": st.column_config.TextColumn("Run"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
            "Total Cost ($)": st.column_config.TextColumn("Total Cost ($)", width="small"),
        },
    )
    st.caption(
        f"{len(rows)} run(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  ${total_cost:.4f} total cost"
    )


def render_agent_success_rank_table(run_id: Optional[str] = None) -> None:
    """Table — agents ranked by success rate (most reliable first).

    Answers "which agents are most reliable?" — distinct from agent-cost-rank
    (sorted by avg cost) and success-breakdown (aggregate totals only).

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Agent Success Rank")

    # agent → [count, success_count, tokens, cost]
    agent_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                agent = ev.get("agent_name") or "unknown"
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if agent not in agent_map:
                    agent_map[agent] = [0, 0, 0, 0.0]
                agent_map[agent][0] += 1
                if success:
                    agent_map[agent][1] += 1
                agent_map[agent][2] += tokens
                agent_map[agent][3] += cost
    else:
        # Mock data: three agents with distinct success rates
        agent_map = {
            "orchestrator": [120, 119, 840_000, 8.0000],
            "research":     [48,  42,  288_000, 12.8800],
            "writer":       [32,  24,  160_000,  1.4400],
        }

    if not agent_map:
        st.info("No delegation events found.")
        return

    rows = []
    for agent, (count, ok, tokens, cost) in agent_map.items():
        failures = count - ok
        avg_cost = cost / count if count > 0 else 0.0
        avg_tokens = tokens / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Agent": agent,
            "Delegations": count,
            "Ok%": f"{ok_pct:.1f}%",
            "Failures": failures,
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Avg Tokens": round(avg_tokens),
        })
    # Sort: ok_pct desc, ties by delegations desc, then agent asc
    rows.sort(key=lambda r: (-float(r["Ok%"].rstrip("%")), -r["Delegations"], r["Agent"]))
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in agent_map.values())
    total_failures = sum(v[0] - v[1] for v in agent_map.values())

    df = pd.DataFrame(rows, columns=["#", "Agent", "Delegations", "Ok%", "Failures", "Avg Cost ($)", "Avg Tokens"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Agent": st.column_config.TextColumn("Agent"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Failures": st.column_config.NumberColumn("Failures", format="%d", width="small"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
        },
    )
    st.caption(
        f"{len(rows)} agent(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_failures} total failures"
    )


def render_model_success_rank_table(run_id: Optional[str] = None) -> None:
    """Table — models ranked by success rate (most reliable first).

    Answers "which model is most reliable?" — mirrors agent-success-rank but
    keyed by the model field.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Model Success Rank")

    # model → [count, success_count, tokens, cost]
    model_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                model = ev.get("model") or "unknown"
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if model not in model_map:
                    model_map[model] = [0, 0, 0, 0.0]
                model_map[model][0] += 1
                if success:
                    model_map[model][1] += 1
                model_map[model][2] += tokens
                model_map[model][3] += cost
    else:
        # Mock data: three models with distinct success rates
        model_map = {
            "claude-haiku-4-5":  [40,  40,  80_000,  0.4800],
            "claude-sonnet-4-6": [142, 138, 946_000, 18.9200],
            "claude-opus-4-6":   [18,  15,  270_000, 14.4000],
        }

    if not model_map:
        st.info("No delegation events found.")
        return

    rows = []
    for model, (count, ok, tokens, cost) in model_map.items():
        failures = count - ok
        avg_cost = cost / count if count > 0 else 0.0
        avg_tokens = tokens / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Model": model,
            "Delegations": count,
            "Ok%": f"{ok_pct:.1f}%",
            "Failures": failures,
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Avg Tokens": round(avg_tokens),
        })
    # Sort: ok_pct desc, ties by delegations desc, then model asc
    rows.sort(key=lambda r: (-float(r["Ok%"].rstrip("%")), -r["Delegations"], r["Model"]))
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in model_map.values())
    total_failures = sum(v[0] - v[1] for v in model_map.values())

    df = pd.DataFrame(rows, columns=["#", "Model", "Delegations", "Ok%", "Failures", "Avg Cost ($)", "Avg Tokens"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Model": st.column_config.TextColumn("Model"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Failures": st.column_config.NumberColumn("Failures", format="%d", width="small"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
        },
    )
    st.caption(
        f"{len(rows)} model(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_failures} total failures"
    )


def render_provider_success_rank_table(run_id: Optional[str] = None) -> None:
    """Table — providers ranked by success rate (most reliable first).

    Answers "which provider is most reliable?" — completes the success-rank trio
    alongside agent-success-rank and model-success-rank.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Provider Success Rank")

    # provider → [count, success_count, tokens, cost]
    provider_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                provider = ev.get("provider") or "unknown"
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if provider not in provider_map:
                    provider_map[provider] = [0, 0, 0, 0.0]
                provider_map[provider][0] += 1
                if success:
                    provider_map[provider][1] += 1
                provider_map[provider][2] += tokens
                provider_map[provider][3] += cost
    else:
        # Mock data: three providers with distinct success rates
        provider_map = {
            "google":    [10,  10,   40_000,  0.2000],
            "anthropic": [160, 155, 1_180_000, 64.0000],
            "openai":    [30,  26,   120_000,   4.5000],
        }

    if not provider_map:
        st.info("No delegation events found.")
        return

    rows = []
    for provider, (count, ok, tokens, cost) in provider_map.items():
        failures = count - ok
        avg_cost = cost / count if count > 0 else 0.0
        avg_tokens = tokens / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Provider": provider,
            "Delegations": count,
            "Ok%": f"{ok_pct:.1f}%",
            "Failures": failures,
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Avg Tokens": round(avg_tokens),
        })
    # Sort: ok_pct desc, ties by delegations desc, then provider asc
    rows.sort(key=lambda r: (-float(r["Ok%"].rstrip("%")), -r["Delegations"], r["Provider"]))
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in provider_map.values())
    total_failures = sum(v[0] - v[1] for v in provider_map.values())

    df = pd.DataFrame(rows, columns=["#", "Provider", "Delegations", "Ok%", "Failures", "Avg Cost ($)", "Avg Tokens"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Provider": st.column_config.TextColumn("Provider"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Failures": st.column_config.NumberColumn("Failures", format="%d", width="small"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
        },
    )
    st.caption(
        f"{len(rows)} provider(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_failures} total failures"
    )


def render_agent_token_rank_table(run_id: Optional[str] = None) -> None:
    """Table — agents ranked by avg tokens per delegation (most token-hungry first).

    Answers "which agent consumes the most tokens per call?" — opens the
    token-rank trio alongside model-token-rank and provider-token-rank.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Agent Token Rank")

    # agent_name → [count, success_count, tokens, cost]
    agent_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                agent = ev.get("agent_name") or "unknown"
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if agent not in agent_map:
                    agent_map[agent] = [0, 0, 0, 0.0]
                agent_map[agent][0] += 1
                if success:
                    agent_map[agent][1] += 1
                agent_map[agent][2] += tokens
                agent_map[agent][3] += cost
    else:
        # Mock data: three agents with distinct avg-token profiles
        agent_map = {
            "builder":    [80, 76, 1_600_000, 48.0000],
            "researcher": [60, 57,   720_000, 18.0000],
            "summarizer": [40, 39,   200_000,  4.0000],
        }

    if not agent_map:
        st.info("No delegation events found.")
        return

    rows = []
    for agent, (count, ok, tokens, cost) in agent_map.items():
        avg_tokens = tokens / count if count > 0 else 0.0
        avg_cost = cost / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Agent": agent,
            "Delegations": count,
            "Avg Tokens": round(avg_tokens),
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Ok%": f"{ok_pct:.1f}%",
            "Total Tokens": tokens,
        })
    # Sort: avg_tok desc, ties by agent name asc
    rows.sort(key=lambda r: (-r["Avg Tokens"], r["Agent"]))
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in agent_map.values())
    total_tokens = sum(v[2] for v in agent_map.values())

    df = pd.DataFrame(rows, columns=["#", "Agent", "Delegations", "Avg Tokens", "Avg Cost ($)", "Ok%", "Total Tokens"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Agent": st.column_config.TextColumn("Agent"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Total Tokens": st.column_config.NumberColumn("Total Tokens", format="%d"),
        },
    )
    st.caption(
        f"{len(rows)} agent(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_tokens:,} total tokens"
    )


def render_model_token_rank_table(run_id: Optional[str] = None) -> None:
    """Table — models ranked by avg tokens per delegation (most token-hungry first).

    Answers "which model consumes the most tokens per call?" — continues the
    token-rank trio alongside agent-token-rank and provider-token-rank.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Model Token Rank")

    # model → [count, success_count, tokens, cost]
    model_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                model = ev.get("model") or "unknown"
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if model not in model_map:
                    model_map[model] = [0, 0, 0, 0.0]
                model_map[model][0] += 1
                if success:
                    model_map[model][1] += 1
                model_map[model][2] += tokens
                model_map[model][3] += cost
    else:
        # Mock data: three models with distinct avg-token profiles
        model_map = {
            "claude-opus-4-5":   [50, 48, 1_000_000, 60.0000],
            "claude-sonnet-4-5": [90, 87,   900_000, 27.0000],
            "claude-haiku-4-5":  [60, 59,   180_000,  3.0000],
        }

    if not model_map:
        st.info("No delegation events found.")
        return

    rows = []
    for model, (count, ok, tokens, cost) in model_map.items():
        avg_tokens = tokens / count if count > 0 else 0.0
        avg_cost = cost / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Model": model,
            "Delegations": count,
            "Avg Tokens": round(avg_tokens),
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Ok%": f"{ok_pct:.1f}%",
            "Total Tokens": tokens,
        })
    # Sort: avg_tok desc, ties by model name asc
    rows.sort(key=lambda r: (-r["Avg Tokens"], r["Model"]))
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in model_map.values())
    total_tokens = sum(v[2] for v in model_map.values())

    df = pd.DataFrame(rows, columns=["#", "Model", "Delegations", "Avg Tokens", "Avg Cost ($)", "Ok%", "Total Tokens"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Model": st.column_config.TextColumn("Model"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Total Tokens": st.column_config.NumberColumn("Total Tokens", format="%d"),
        },
    )
    st.caption(
        f"{len(rows)} model(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_tokens:,} total tokens"
    )


def render_provider_token_rank_table(run_id: Optional[str] = None) -> None:
    """Table — providers ranked by avg tokens per delegation (most token-hungry first).

    Answers "which provider consumes the most tokens per call?" — completes the
    token-rank trio alongside agent-token-rank and model-token-rank.

    Args:
        run_id: Optional run ID to filter. ``None`` means all runs.
    """
    st.subheader("Provider Token Rank")

    # provider → [count, success_count, tokens, cost]
    provider_map: dict = {}

    log_path = _delegation_log_path()
    if log_path.exists():
        with log_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("event_type") != "DelegationEnd":
                    continue
                if run_id and ev.get("run_id") != run_id:
                    continue
                provider = ev.get("provider") or "unknown"
                success = bool(ev.get("success", False))
                tokens = int(ev.get("tokens_used", 0) or 0)
                cost = float(ev.get("cost_usd", 0.0) or 0.0)
                if provider not in provider_map:
                    provider_map[provider] = [0, 0, 0, 0.0]
                provider_map[provider][0] += 1
                if success:
                    provider_map[provider][1] += 1
                provider_map[provider][2] += tokens
                provider_map[provider][3] += cost
    else:
        # Mock data: three providers with distinct avg-token profiles
        provider_map = {
            "anthropic": [160, 155, 1_440_000, 72.0000],
            "openai":    [30,  28,   150_000,   4.5000],
            "google":    [10,  10,    30_000,   0.3000],
        }

    if not provider_map:
        st.info("No delegation events found.")
        return

    rows = []
    for provider, (count, ok, tokens, cost) in provider_map.items():
        avg_tokens = tokens / count if count > 0 else 0.0
        avg_cost = cost / count if count > 0 else 0.0
        ok_pct = 100.0 * ok / count if count > 0 else 0.0
        rows.append({
            "Provider": provider,
            "Delegations": count,
            "Avg Tokens": round(avg_tokens),
            "Avg Cost ($)": f"{avg_cost:.4f}",
            "Ok%": f"{ok_pct:.1f}%",
            "Total Tokens": tokens,
        })
    # Sort: avg_tok desc, ties by provider name asc
    rows.sort(key=lambda r: (-r["Avg Tokens"], r["Provider"]))
    for i, r in enumerate(rows, 1):
        r["#"] = i

    total_delegations = sum(v[0] for v in provider_map.values())
    total_tokens = sum(v[2] for v in provider_map.values())

    df = pd.DataFrame(rows, columns=["#", "Provider", "Delegations", "Avg Tokens", "Avg Cost ($)", "Ok%", "Total Tokens"])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Provider": st.column_config.TextColumn("Provider"),
            "Delegations": st.column_config.NumberColumn("Delegations", format="%d"),
            "Avg Tokens": st.column_config.NumberColumn("Avg Tokens", format="%d"),
            "Avg Cost ($)": st.column_config.TextColumn("Avg Cost ($)", width="small"),
            "Ok%": st.column_config.TextColumn("Ok%", width="small"),
            "Total Tokens": st.column_config.NumberColumn("Total Tokens", format="%d"),
        },
    )
    st.caption(
        f"{len(rows)} provider(s)  \u2022  {total_delegations} total delegations  "
        f"\u2022  {total_tokens:,} total tokens"
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
