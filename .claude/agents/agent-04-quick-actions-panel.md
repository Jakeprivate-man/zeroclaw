---
name: Agent 04 - QuickActionsPanel Component
description: Build QuickActionsPanel with 16 administrative action buttons
agent_type: streamlit-component
phase: 2
dependencies: [agent-23, agent-24]
priority: high
---

# Agent 04: QuickActionsPanel Component

## Task Overview
Create the QuickActionsPanel component with 16 action buttons organized in 4 categories.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Official Streamlit Documentation

### st.button
```python
if st.button(label, key=None, help=None, on_click=None, use_container_width=False):
    # Button clicked
```

**Parameters:**
- `label` (str): Button text
- `key` (str): Unique identifier
- `on_click` (callable): Callback function
- `use_container_width` (bool): Expand to container width

**Returns:** `bool` - True if clicked on last run

### st.columns
```python
col1, col2, col3, col4 = st.columns(4)
```
Create 4 equal-width columns for button grid.

## Context: React QuickActionsPanel Component

The React version (`web-ui/src/components/dashboard/QuickActionsPanel.tsx`) has:

**4 Categories with 4 Actions Each:**

1. **System Controls**
   - 🔄 Restart Gateway
   - 🗑️ Clear Cache
   - 📊 Refresh Stats
   - 📜 View Logs

2. **Agent Controls**
   - ▶️ Start All
   - ⏸️ Pause All
   - 🔁 Restart Failed
   - 🗑️ Clear Queue

3. **Data Management**
   - 💾 Backup Data
   - 🔄 Sync Remote
   - 📦 Compact DB
   - 📤 Export Logs

4. **Reports & Analysis**
   - 📊 System Report
   - 📈 Analytics
   - 🔍 Diagnostics
   - 📧 Email Summary

**Features:**
- Loading states during execution
- Success/error feedback
- Activity logging
- Simulated delays (1-2s)

## Implementation Requirements

Create `components/dashboard/quick_actions_panel.py`:

```python
import streamlit as st
import time
from lib.session_state import add_activity

def render():
    """Render quick actions panel with 16 action buttons."""

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

def handle_action(action_id, message):
    """Handle action button click with feedback."""
    # Show loading message
    with st.spinner(message):
        # Simulate processing time
        time.sleep(1.5)

        # Log activity
        add_activity({
            'id': f"action-{int(time.time())}",
            'type': 'info',
            'icon': '⚡',
            'message': f"Action completed: {action_id}",
            'timestamp': time.time()
        })

    # Show success message
    st.success(f"✅ {message.replace('...', '')} complete!")
    time.sleep(0.5)
    st.rerun()
```

## Requirements

1. **16 buttons**: 4 categories × 4 actions each
2. **Grid layout**: 4 columns per row
3. **Full width buttons**: Use `use_container_width=True`
4. **Loading states**: Show spinner during execution
5. **Feedback**: Success messages after completion
6. **Activity logging**: Add activity to stream
7. **Unique keys**: Each button needs unique key
8. **Icons**: Emoji icons for each action

## Deliverables

1. `components/dashboard/quick_actions_panel.py` - Complete implementation
2. Action handler with loading simulation
3. Integration with activity stream

Now implement this component.
