"""QuickActionsPanel component for ZeroClaw Streamlit Dashboard.

This component provides 16 administrative action buttons organized into 4 categories:
- System Controls (4 actions)
- Agent Controls (4 actions)
- Data Management (4 actions)
- Reports & Analysis (4 actions)

Each button triggers a simulated action with loading state, success feedback,
and activity logging.
"""

import streamlit as st
import time
from lib.session_state import add_activity


def render():
    """Render quick actions panel with 16 action buttons.

    Displays a grid of action buttons organized by category with full-width
    buttons, loading states, success feedback, and activity stream integration.
    """
    st.subheader("⚡ Quick Actions")

    # System Controls
    st.markdown("**System Controls**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔄 Restart Gateway", use_container_width=True, key="restart_gateway"):
            handle_action("restart-gateway", "Restarting gateway...")

    with col2:
        if st.button("🗑️ Clear Cache", use_container_width=True, key="clear_cache"):
            handle_action("clear-cache", "Clearing cache...")

    with col3:
        if st.button("📊 Refresh Stats", use_container_width=True, key="refresh_stats"):
            handle_action("refresh-stats", "Refreshing statistics...")

    with col4:
        if st.button("📜 View Logs", use_container_width=True, key="view_logs"):
            handle_action("view-logs", "Opening logs...")

    st.divider()

    # Agent Controls
    st.markdown("**Agent Controls**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("▶️ Start All", use_container_width=True, key="start_all"):
            handle_action("start-all-agents", "Starting all agents...")

    with col2:
        if st.button("⏸️ Pause All", use_container_width=True, key="pause_all"):
            handle_action("pause-all-agents", "Pausing all agents...")

    with col3:
        if st.button("🔁 Restart Failed", use_container_width=True, key="restart_failed"):
            handle_action("restart-failed", "Restarting failed agents...")

    with col4:
        if st.button("🗑️ Clear Queue", use_container_width=True, key="clear_queue"):
            handle_action("clear-queue", "Clearing task queue...")

    st.divider()

    # Data Management
    st.markdown("**Data Management**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("💾 Backup Data", use_container_width=True, key="backup_data"):
            handle_action("backup-data", "Creating backup...")

    with col2:
        if st.button("🔄 Sync Remote", use_container_width=True, key="sync_remote"):
            handle_action("sync-remote", "Syncing with remote...")

    with col3:
        if st.button("📦 Compact DB", use_container_width=True, key="compact_db"):
            handle_action("compact-db", "Compacting database...")

    with col4:
        if st.button("📤 Export Logs", use_container_width=True, key="export_logs"):
            handle_action("export-logs", "Exporting logs...")

    st.divider()

    # Reports & Analysis
    st.markdown("**Reports & Analysis**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("📊 System Report", use_container_width=True, key="system_report"):
            handle_action("generate-system-report", "Generating system report...")

    with col2:
        if st.button("📈 Analytics", use_container_width=True, key="analytics_report"):
            handle_action("generate-analytics", "Generating analytics...")

    with col3:
        if st.button("🔍 Diagnostics", use_container_width=True, key="diagnostics"):
            handle_action("run-diagnostics", "Running diagnostics...")

    with col4:
        if st.button("📧 Email Summary", use_container_width=True, key="email_summary"):
            handle_action("email-summary", "Sending email summary...")


def handle_action(action_id: str, message: str):
    """Handle action button click with feedback and activity logging.

    Args:
        action_id: Unique identifier for the action (e.g., 'restart-gateway')
        message: Loading message to display during execution
    """
    # Show loading message with spinner
    with st.spinner(message):
        # Simulate processing time (1-2 seconds as per React version)
        time.sleep(1.5)

        # Log activity to the activity stream
        add_activity(
            activity_type='info',
            message=f"Action completed: {action_id}",
            icon='⚡',
            metadata={'action_id': action_id}
        )

    # Show success message
    st.success(f"✅ {message.replace('...', '')} complete!")

    # Brief pause to show success message
    time.sleep(0.5)

    # Rerun to update UI and activity stream
    st.rerun()
