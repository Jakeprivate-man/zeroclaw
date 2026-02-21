"""Delegation Tree Visualization Component.

Displays nested agent delegation hierarchy with interactive tree view.
Shows delegation depth, duration, success/failure status, and model used.

Supports run-level filtering: each ZeroClaw process invocation has a unique
`run_id`, and the selector lets users view delegations from a specific run.
"""

import streamlit as st
from typing import List, Optional
from lib.delegation_parser import DelegationParser, DelegationNode


def render_delegation_tree(
    run_id: Optional[str] = None,
    use_mock_data: bool = False,
    show_run_selector: bool = True,
) -> None:
    """Render delegation tree visualization.

    Args:
        run_id: Optional run ID to filter delegations. If None and
                show_run_selector is True, a selector is shown in the UI.
        use_mock_data: If True, use mock data for demonstration.
        show_run_selector: If True, render a run selector dropdown above the tree.
    """
    st.subheader("🌳 Delegation Tree")
    st.caption("Visualize nested agent delegations and their execution status")

    parser = DelegationParser()

    if use_mock_data:
        roots = parser.get_mock_tree()
        st.info("📊 Showing mock delegation data for demonstration")
        for root in roots:
            _render_node(root, depth=0, is_last=True)
        return

    # Run selector
    selected_run_id = run_id
    if show_run_selector and run_id is None:
        runs = parser.list_runs()
        if runs:
            options = ["All runs"] + [r.run_id for r in runs]
            labels = ["All runs"] + [r.label for r in runs]

            # Map label → run_id for selectbox
            label_to_run = {"All runs": None}
            for r in runs:
                label_to_run[r.run_id] = r.run_id

            selected_label = st.selectbox(
                "Filter by run",
                options=labels,
                index=1 if len(labels) > 1 else 0,  # Default to most recent run
                help="Each ZeroClaw process invocation has a unique run ID. "
                     "Select a run to view only its delegations.",
                key="delegation_run_selector",
            )
            # Map selected label back to run_id
            if selected_label == "All runs":
                selected_run_id = None
            else:
                # Find the run_id matching the label
                for r in runs:
                    if r.label == selected_label:
                        selected_run_id = r.run_id
                        break

            # Show run info if specific run selected
            if selected_run_id:
                matching = [r for r in runs if r.run_id == selected_run_id]
                if matching:
                    run = matching[0]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.caption(f"Run ID: `{run.run_id[:16]}…`")
                    with col2:
                        ts = run.start_time.strftime("%H:%M:%S") if run.start_time else "?"
                        st.caption(f"Started: {ts}")
                    with col3:
                        st.caption(f"Delegations: {run.total_delegations}")

    # Fetch tree
    roots = parser.parse_delegation_tree(selected_run_id)

    if not roots:
        st.warning(
            "No delegation events found. "
            "Delegations appear here when agents delegate work to sub-agents."
        )
        st.markdown("---")
        st.markdown("**Example delegation tree (mock):**")
        roots = parser.get_mock_tree()

    for root in roots:
        _render_node(root, depth=0, is_last=True)


def _render_node(node: DelegationNode, depth: int, is_last: bool) -> None:
    """Recursively render a delegation node and its children.

    Args:
        node: Node to render
        depth: Current depth in tree
        is_last: Whether this is the last child of its parent
    """
    if depth == 0:
        connector = ""
        prefix = ""
    else:
        connector = "└─" if is_last else "├─"
        prefix = "   " * (depth - 1)

    duration_str = ""
    if node.duration_ms is not None:
        if node.duration_ms < 1000:
            duration_str = f"{node.duration_ms}ms"
        else:
            duration_str = f"{node.duration_ms / 1000:.2f}s"

    agent_type = "🤖 Agentic" if node.agentic else "🔧 Simple"
    model_short = node.model.split('/')[-1] if '/' in node.model else node.model

    with st.expander(
        f"{prefix}{connector} {node.status} **{node.agent_name}** ({agent_type}, {model_short}) {duration_str}",
        expanded=(depth < 2)
    ):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Agent:** `{node.agent_name}`")
            st.markdown(f"**Provider:** `{node.provider}`")
            st.markdown(f"**Model:** `{node.model}`")

        with col2:
            st.markdown(f"**Depth:** `{node.depth}`")
            st.markdown(f"**Type:** `{'Agentic' if node.agentic else 'Simple'}`")
            if node.duration_ms:
                st.markdown(f"**Duration:** `{duration_str}`")
            if node.run_id:
                st.markdown(f"**Run:** `{node.run_id[:16]}…`")

        if node.is_complete:
            if node.success:
                st.success("✅ Delegation completed successfully")
            else:
                st.error(f"❌ Delegation failed: {node.error_message or 'Unknown error'}")
        else:
            st.info("🟡 Delegation in progress...")

        if node.start_time:
            st.caption(f"Started: {node.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if node.end_time:
            st.caption(f"Ended: {node.end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if node.is_complete and node.children:
            total_child_duration = sum(
                c.duration_ms for c in node.children if c.duration_ms
            )
            st.metric(
                "Total Child Duration",
                f"{total_child_duration}ms" if total_child_duration < 1000
                else f"{total_child_duration / 1000:.2f}s"
            )

    if node.children:
        for i, child in enumerate(node.children):
            _render_node(child, depth + 1, is_last=(i == len(node.children) - 1))


def render_delegation_summary(run_id: Optional[str] = None) -> None:
    """Render summary metrics for delegations.

    Args:
        run_id: Optional run ID to filter delegations.
    """
    parser = DelegationParser()
    roots = parser.parse_delegation_tree(run_id)

    if not roots:
        roots = parser.get_mock_tree()

    all_nodes: List[DelegationNode] = []

    def collect_nodes(node: DelegationNode) -> None:
        all_nodes.append(node)
        for child in node.children:
            collect_nodes(child)

    for root in roots:
        collect_nodes(root)

    total_delegations = len(all_nodes)
    completed = sum(1 for n in all_nodes if n.is_complete)
    successful = sum(1 for n in all_nodes if n.success)
    failed = sum(1 for n in all_nodes if n.is_complete and not n.success)
    max_depth = max((n.depth for n in all_nodes), default=0)
    distinct_runs = len({n.run_id for n in all_nodes if n.run_id})

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Total Delegations",
            total_delegations,
            help="Total number of delegation events"
        )

    with col2:
        success_rate = (successful / completed * 100) if completed > 0 else 0
        st.metric(
            "Success Rate",
            f"{success_rate:.1f}%",
            delta=f"+{successful}/{completed}",
            help="Percentage of successful delegations"
        )

    with col3:
        st.metric(
            "Failed",
            failed,
            delta=f"-{failed}" if failed > 0 else "0",
            delta_color="inverse",
            help="Number of failed delegations"
        )

    with col4:
        st.metric(
            "Max Depth",
            max_depth,
            help="Maximum delegation tree depth"
        )

    with col5:
        st.metric(
            "Runs",
            distinct_runs,
            help="Number of distinct process runs in log"
        )
