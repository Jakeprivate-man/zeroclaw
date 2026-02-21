"""Delegation Tree Visualization Component.

Displays nested agent delegation hierarchy with interactive tree view.
Shows delegation depth, duration, success/failure status, and model used.
"""

import streamlit as st
from typing import List, Optional
from lib.delegation_parser import DelegationParser, DelegationNode


def render_delegation_tree(
    session_id: Optional[str] = None,
    use_mock_data: bool = False
) -> None:
    """Render delegation tree visualization.

    Args:
        session_id: Optional session ID to filter delegations
        use_mock_data: If True, use mock data for demonstration
    """
    st.subheader("🌳 Delegation Tree")
    st.caption("Visualize nested agent delegations and their execution status")

    # Initialize parser
    parser = DelegationParser()

    # Get delegation tree
    if use_mock_data:
        roots = parser.get_mock_tree()
        st.info("📊 Showing mock delegation data for demonstration")
    else:
        roots = parser.parse_delegation_tree(session_id)
        if not roots:
            st.warning("No delegation events found. Delegations will appear here when agents delegate work to sub-agents.")
            # Show mock data as example
            st.markdown("---")
            st.markdown("**Example delegation tree:**")
            roots = parser.get_mock_tree()

    # Render each root node
    for root in roots:
        _render_node(root, depth=0, is_last=True)


def _render_node(node: DelegationNode, depth: int, is_last: bool) -> None:
    """Recursively render a delegation node and its children.

    Args:
        node: Node to render
        depth: Current depth in tree
        is_last: Whether this is the last child of its parent
    """
    # Build tree connector string
    if depth == 0:
        connector = ""
        prefix = ""
    else:
        connector = "└─" if is_last else "├─"
        prefix = "   " * (depth - 1)

    # Format duration
    duration_str = ""
    if node.duration_ms is not None:
        if node.duration_ms < 1000:
            duration_str = f"{node.duration_ms}ms"
        else:
            duration_str = f"{node.duration_ms / 1000:.2f}s"

    # Build display string
    agent_type = "🤖 Agentic" if node.agentic else "🔧 Simple"
    model_short = node.model.split('/')[-1] if '/' in node.model else node.model

    # Create expander for each node
    with st.expander(
        f"{prefix}{connector} {node.status} **{node.agent_name}** ({agent_type}, {model_short}) {duration_str}",
        expanded=(depth < 2)  # Auto-expand first 2 levels
    ):
        # Node details
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

        # Status indicators
        if node.is_complete:
            if node.success:
                st.success("✅ Delegation completed successfully")
            else:
                st.error(f"❌ Delegation failed: {node.error_message or 'Unknown error'}")
        else:
            st.info("🟡 Delegation in progress...")

        # Timeline if available
        if node.start_time:
            st.caption(f"Started: {node.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if node.end_time:
            st.caption(f"Ended: {node.end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Metrics
        if node.is_complete and node.children:
            total_child_duration = sum(
                c.duration_ms for c in node.children if c.duration_ms
            )
            st.metric(
                "Total Child Duration",
                f"{total_child_duration}ms" if total_child_duration < 1000
                else f"{total_child_duration / 1000:.2f}s"
            )

    # Render children
    if node.children:
        for i, child in enumerate(node.children):
            _render_node(child, depth + 1, is_last=(i == len(node.children) - 1))


def render_delegation_summary(session_id: Optional[str] = None) -> None:
    """Render summary metrics for delegations.

    Args:
        session_id: Optional session ID to filter delegations
    """
    parser = DelegationParser()
    roots = parser.parse_delegation_tree(session_id)

    if not roots:
        # Use mock data for demo
        roots = parser.get_mock_tree()

    # Flatten tree to get all nodes
    all_nodes = []
    def collect_nodes(node):
        all_nodes.append(node)
        for child in node.children:
            collect_nodes(child)

    for root in roots:
        collect_nodes(root)

    # Calculate metrics
    total_delegations = len(all_nodes)
    completed = sum(1 for n in all_nodes if n.is_complete)
    successful = sum(1 for n in all_nodes if n.success)
    failed = sum(1 for n in all_nodes if n.is_complete and not n.success)
    max_depth = max((n.depth for n in all_nodes), default=0)

    # Render metrics
    col1, col2, col3, col4 = st.columns(4)

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
