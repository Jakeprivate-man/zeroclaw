---
name: Agent 17 - Dashboard Page Orchestration
description: Integrate all dashboard components into complete Dashboard page
agent_type: streamlit-page
phase: 2
dependencies: [agent-01, agent-02, agent-03, agent-04]
priority: high
---

# Agent 17: Dashboard Page Orchestration

## Task Overview
Create the Dashboard page that integrates all 4 dashboard components into a cohesive layout.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Official Streamlit Documentation

### st.columns
```python
col1, col2 = st.columns([3, 1])  # Proportional widths
col1, col2 = st.columns(2)  # Equal widths
```

### st.title / st.caption
```python
st.title("Dashboard")
st.caption("Description text")
```

## Context: React Dashboard Page

The React version (`web-ui/src/pages/Dashboard.tsx`) has:

**Layout:**
```
┌─────────────────────────────────────┐
│ Dashboard                           │
│ Real-time monitoring...             │
├─────────────────────────────────────┤
│ RealTimeMetrics (4 metric cards)   │
├─────────────────────────────────────┤
│ QuickActionsPanel (16 buttons)     │
├─────────────────────────────────────┤
│ ActivityStream    │ AgentStatusMon  │
│  (left column)   │  (right column)  │
└─────────────────────────────────────┘
```

## Implementation Requirements

Create `pages/dashboard.py`:

```python
import streamlit as st
from components.dashboard.real_time_metrics import render as render_metrics
from components.dashboard.quick_actions_panel import render as render_actions
from components.dashboard.activity_stream import render as render_activity
from components.dashboard.agent_status_monitor import render as render_agents

def render():
    """Render the complete Dashboard page."""

    # Page header
    st.title("📊 Dashboard")
    st.caption("Real-time monitoring of ZeroClaw agent activity and system health")

    st.divider()

    # Real-Time Metrics - 4 metric cards with sparklines
    render_metrics()

    st.divider()

    # Quick Actions Panel - 16 action buttons
    render_actions()

    st.divider()

    # Activity Stream and Agent Status - Side by side
    col1, col2 = st.columns(2)

    with col1:
        # Activity Stream - Live feed of system events
        render_activity()

    with col2:
        # Agent Status Monitor - Individual agent health
        render_agents()
```

## Requirements

1. **Import all 4 components**: real_time_metrics, activity_stream, agent_status_monitor, quick_actions_panel
2. **Page header**: Title and caption
3. **Vertical sections**: Metrics, actions, then 2-column layout
4. **Dividers**: Separate sections visually
5. **Responsive**: 2 columns on desktop, stack on mobile
6. **Clean render function**: Can be called from app.py routing

## Deliverables

1. `pages/dashboard.py` - Complete dashboard page
2. Proper component imports
3. Clean layout structure

Now implement this page.
