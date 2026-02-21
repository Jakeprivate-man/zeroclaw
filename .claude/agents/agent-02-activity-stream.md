---
name: Agent 02 - ActivityStream Component
description: Build ActivityStream component with real-time event feed and filtering
agent_type: streamlit-component
phase: 2
dependencies: [agent-23, agent-24]
priority: high
---

# Agent 02: ActivityStream Component

## Task Overview
Create the ActivityStream component that displays a real-time scrollable event feed with filtering and auto-scroll.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Official Streamlit Documentation

### st.container
```python
st.container(*, height=300, border=True)
```
Create a scrollable container with fixed height.

**Parameters:**
- `height` (int): Fixed pixel height - container scrolls if content exceeds
- `border` (bool): Show border around container

**Important:** "Avoid heights exceeding 500 pixels" on mobile

### st.selectbox
```python
st.selectbox(label, options, index=0)
```
Display a select widget for filtering.

### st.checkbox
```python
st.checkbox(label, value=False)
```
Display a checkbox for auto-scroll toggle.

## Context: React ActivityStream Component

The React version (`web-ui/src/components/dashboard/ActivityStream.tsx`) shows:

**Features:**
- Scrollable event feed (max 100 activities)
- Filter by activity type (all, agent_started, agent_stopped, analysis_complete, report_generated, error, warning, info)
- Auto-scroll toggle
- Clear all button
- Time-relative timestamps (e.g., "2 minutes ago")
- Color-coded events with icons

**Activity Types:**
- agent_started (🟢)
- agent_stopped (🔴)
- analysis_complete (✅)
- report_generated (📄)
- error (❌)
- warning (⚠️)
- info (ℹ️)

## Implementation Requirements

Create `components/dashboard/activity_stream.py`:

```python
import streamlit as st
from datetime import datetime
from lib.session_state import get_state, add_activity
from lib.mock_data import generate_mock_activity

def render():
    """Render the activity stream with filtering and auto-scroll."""

    st.subheader("📋 Activity Stream")

    # Controls row
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        activity_filter = st.selectbox(
            "Filter",
            ["all", "agent_started", "agent_stopped", "analysis_complete",
             "report_generated", "error", "warning", "info"],
            index=0,
            label_visibility="collapsed"
        )

    with col2:
        auto_scroll = st.checkbox("Auto-scroll", value=True)

    with col3:
        if st.button("Clear All"):
            st.session_state.activities = []
            st.rerun()

    # Get activities
    activities = get_state('activities', [])

    # Filter activities
    if activity_filter != "all":
        filtered_activities = [a for a in activities if a['type'] == activity_filter]
    else:
        filtered_activities = activities

    # Scrollable container
    with st.container(height=500, border=True):
        if len(filtered_activities) == 0:
            st.caption("No activities to display")
        else:
            # Reverse to show newest first
            for activity in reversed(filtered_activities[-50:]):  # Last 50
                render_activity_item(activity)

    # Generate mock activity (for testing)
    if st.button("+ Generate Test Activity", key="gen_activity"):
        new_activity = generate_mock_activity()
        add_activity(new_activity)
        st.rerun()

def render_activity_item(activity):
    """Render a single activity item."""
    icon = activity.get('icon', 'ℹ️')
    message = activity.get('message', 'Activity')
    timestamp = activity.get('timestamp', datetime.now().timestamp())
    activity_type = activity.get('type', 'info')

    # Calculate time ago
    time_ago = format_time_ago(timestamp)

    # Color based on type
    color_map = {
        'error': '#FF5555',
        'warning': '#F1FA8C',
        'agent_started': '#5FAF87',
        'agent_stopped': '#FF5555',
        'analysis_complete': '#87D7AF',
        'report_generated': '#87D7AF',
        'info': '#87D7AF'
    }
    color = color_map.get(activity_type, '#87D7AF')

    # Render activity
    st.markdown(f"""
    <div style="padding: 0.5rem; margin-bottom: 0.5rem; border-left: 3px solid {color};">
        <div style="color: {color}; font-weight: bold;">
            {icon} {message}
        </div>
        <div style="font-size: 0.8rem; color: #888; margin-top: 0.25rem;">
            {time_ago}
        </div>
    </div>
    """, unsafe_allow_html=True)

def format_time_ago(timestamp):
    """Format timestamp as 'X ago' string."""
    now = datetime.now().timestamp()
    diff = int(now - timestamp)

    if diff < 60:
        return "Just now"
    elif diff < 3600:
        minutes = diff // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif diff < 86400:
        hours = diff // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    else:
        days = diff // 86400
        return f"{days} day{'s' if days > 1 else ''} ago"
```

## Requirements

1. **Scrollable container**: Fixed 500px height with overflow scroll
2. **Filtering**: Dropdown to filter by activity type
3. **Auto-scroll**: Checkbox to enable/disable auto-scroll to bottom
4. **Clear all**: Button to clear activity history
5. **Time formatting**: Relative time strings ("2 minutes ago")
6. **Color-coding**: Different colors for different activity types
7. **Icons**: Emoji icons for each activity type

## Deliverables

1. `components/dashboard/activity_stream.py` - Complete implementation
2. Helper function for time formatting
3. Test with mock activities

Now implement this component.
