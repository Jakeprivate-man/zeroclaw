"""Live Metrics Component - Team 2: Live Dashboard Data

Displays real agent state and activity using actual data sources.
Replaces mock data with real process monitoring and memory reading.
"""

import streamlit as st
from typing import Dict, Any
from datetime import datetime
import logging

from lib.process_monitor import process_monitor
from lib.memory_reader import memory_reader, costs_reader
from lib.tool_history_parser import tool_history_parser

logger = logging.getLogger(__name__)


def render_live_metrics():
    """Render live metrics dashboard."""
    st.header("Live Agent Metrics")

    # Auto-refresh toggle
    auto_refresh = st.toggle("Auto-refresh (5s)", value=True)

    if auto_refresh:
        st.session_state.metrics_refresh = True

    # Refresh button
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("Refresh Now", use_container_width=True):
            st.rerun()

    # Display metrics in tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Processes", "Memory", "Costs", "Tools"
    ])

    with tab1:
        render_process_metrics()

    with tab2:
        render_memory_metrics()

    with tab3:
        render_cost_metrics()

    with tab4:
        render_tool_metrics()

    # Auto-refresh logic
    if auto_refresh:
        import time
        time.sleep(5)
        st.rerun()


def render_process_metrics():
    """Render process monitoring metrics."""
    st.subheader("Running Processes")

    try:
        # Get all ZeroClaw processes
        processes = process_monitor.list_all_processes()

        if not processes:
            st.info("No ZeroClaw processes currently running")
            return

        # Display process table
        process_data = []
        for proc in processes:
            process_data.append({
                "PID": proc.pid,
                "Name": proc.name,
                "Status": proc.status,
                "CPU %": f"{proc.cpu_percent:.1f}",
                "Memory (MB)": f"{proc.memory_mb:.1f}",
                "Started": proc.created.strftime("%H:%M:%S")
            })

        st.dataframe(process_data, use_container_width=True)

        # System stats
        st.divider()
        st.subheader("System Resources")

        stats = process_monitor.get_system_stats()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "CPU Usage",
                f"{stats.get('cpu_percent', 0):.1f}%"
            )

        with col2:
            st.metric(
                "Memory Usage",
                f"{stats.get('memory_percent', 0):.1f}%",
                delta=f"{stats.get('memory_used_gb', 0):.1f} GB"
            )

        with col3:
            st.metric(
                "Disk Usage",
                f"{stats.get('disk_percent', 0):.1f}%",
                delta=f"{stats.get('disk_used_gb', 0):.1f} GB"
            )

    except Exception as e:
        st.error(f"Error loading process metrics: {e}")
        logger.error(f"Process metrics error: {e}")


def render_memory_metrics():
    """Render memory store metrics."""
    st.subheader("Memory Store")

    try:
        # Get memory stats
        stats = memory_reader.get_stats()

        if not stats.get('file_exists'):
            st.warning("Memory store file not found")
            return

        # Display stats
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Entries", stats.get('entry_count', 0))

        with col2:
            st.metric("File Size", f"{stats.get('file_size_kb', 0):.1f} KB")

        with col3:
            last_mod = stats.get('last_modified')
            if last_mod:
                st.metric("Last Modified", last_mod.strftime("%H:%M:%S"))

        # Display memory entries
        st.divider()

        # Search box
        search_query = st.text_input("Search memory:", placeholder="Enter key or value...")

        if search_query:
            entries = memory_reader.search_memory(search_query)
            st.info(f"Found {len(entries)} matching entries")
        else:
            entries = memory_reader.get_all_entries()

        # Display entries table
        if entries:
            entry_data = []
            for entry in entries[:50]:  # Limit to 50 for performance
                entry_data.append({
                    "Key": entry.key,
                    "Value": entry.value[:100] + "..." if len(entry.value) > 100 else entry.value,
                    "Category": entry.category or "default",
                    "Timestamp": entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                })

            st.dataframe(entry_data, use_container_width=True)

            if len(entries) > 50:
                st.caption(f"Showing 50 of {len(entries)} entries")
        else:
            st.info("No memory entries found")

    except Exception as e:
        st.error(f"Error loading memory metrics: {e}")
        logger.error(f"Memory metrics error: {e}")


def render_cost_metrics():
    """Render cost tracking metrics."""
    st.subheader("Cost Tracking")

    try:
        # Get today's costs
        daily_summary = costs_reader.get_daily_summary()

        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Today's Cost",
                f"${daily_summary.get('total_cost_usd', 0):.4f}"
            )

        with col2:
            st.metric(
                "Total Tokens",
                f"{daily_summary.get('total_tokens', 0):,}"
            )

        with col3:
            st.metric(
                "Requests",
                daily_summary.get('request_count', 0)
            )

        with col4:
            # Calculate average cost per request
            avg_cost = (
                daily_summary.get('total_cost_usd', 0) /
                max(daily_summary.get('request_count', 1), 1)
            )
            st.metric(
                "Avg Cost/Request",
                f"${avg_cost:.4f}"
            )

        # Monthly summary
        st.divider()
        st.subheader("Monthly Summary")

        now = datetime.now()
        monthly_summary = costs_reader.get_monthly_summary(now.year, now.month)

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Month Total",
                f"${monthly_summary.get('total_cost_usd', 0):.2f}"
            )

        with col2:
            st.metric(
                "Month Requests",
                monthly_summary.get('request_count', 0)
            )

        # By model breakdown
        st.divider()
        st.subheader("Cost by Model")

        by_model = monthly_summary.get('by_model', {})
        if by_model:
            model_data = []
            for model, data in by_model.items():
                model_data.append({
                    "Model": model.split('/')[-1],  # Show short name
                    "Cost": f"${data['cost']:.4f}",
                    "Tokens": f"{data['tokens']:,}",
                    "Requests": data['count']
                })

            st.dataframe(model_data, use_container_width=True)
        else:
            st.info("No cost data available")

    except Exception as e:
        st.error(f"Error loading cost metrics: {e}")
        logger.error(f"Cost metrics error: {e}")


def render_tool_metrics():
    """Render tool execution metrics."""
    st.subheader("Tool Execution History")

    try:
        # Get tool stats
        stats = tool_history_parser.get_tool_stats()

        # Display summary metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Total Executions",
                stats.get('total_executions', 0)
            )

        with col2:
            st.metric(
                "Success Rate",
                f"{stats.get('success_rate', 0):.1f}%"
            )

        with col3:
            # Count dangerous tools
            danger_counts = stats.get('tools_by_danger', {})
            dangerous = danger_counts.get('HIGH', 0) + danger_counts.get('CRITICAL', 0)
            st.metric(
                "Dangerous Tools",
                dangerous
            )

        # Recent executions
        st.divider()
        st.subheader("Recent Executions")

        recent = tool_history_parser.get_recent_tools(count=20)

        if recent:
            exec_data = []
            for exec in recent:
                exec_data.append({
                    "Tool": exec.tool_name,
                    "Success": "✅" if exec.success else "❌",
                    "Duration": f"{exec.duration_ms:.0f}ms",
                    "Danger": exec.danger_level.name,
                    "Approved": "✅" if exec.approved else "❌",
                    "Time": exec.timestamp.strftime("%H:%M:%S")
                })

            st.dataframe(exec_data, use_container_width=True)
        else:
            st.info("No tool executions recorded")

        # Tool usage breakdown
        st.divider()
        st.subheader("Tool Usage")

        tools_by_name = stats.get('tools_by_name', {})
        if tools_by_name:
            tool_data = []
            for name, data in sorted(tools_by_name.items(), key=lambda x: x[1]['count'], reverse=True):
                success_rate = (data['successes'] / max(data['count'], 1)) * 100
                tool_data.append({
                    "Tool": name,
                    "Count": data['count'],
                    "Success Rate": f"{success_rate:.0f}%",
                    "Failures": data['failures']
                })

            st.dataframe(tool_data, use_container_width=True)
        else:
            st.info("No tool usage data")

    except Exception as e:
        st.error(f"Error loading tool metrics: {e}")
        logger.error(f"Tool metrics error: {e}")
