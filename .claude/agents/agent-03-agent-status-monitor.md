---
name: Agent 03 - AgentStatusMonitor Component
description: Build AgentStatusMonitor component showing individual agent health cards
agent_type: streamlit-component
phase: 2
dependencies: [agent-23, agent-24]
priority: high
---

# Agent 03: AgentStatusMonitor Component

## Task Overview
Create the AgentStatusMonitor component that displays individual agent health cards with status, CPU, memory, and task metrics.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Official Streamlit Documentation

### st.columns
```python
col1, col2 = st.columns([3, 1])
```
Create side-by-side columns with proportional widths.

### st.container
```python
with st.container(border=True):
    st.write("Content")
```
Group content with optional border.

### st.markdown
```python
st.markdown(html_content, unsafe_allow_html=True)
```
Render custom HTML/CSS for styling.

## Context: React AgentStatusMonitor Component

The React version (`web-ui/src/components/dashboard/AgentStatusMonitor.tsx`) displays:

**Agent Card Metrics:**
- Agent name with icon
- Status badge (active, idle, error, stopped)
- Health indicator (healthy, warning, critical)
- CPU usage percentage
- Memory usage (formatted bytes)
- Uptime (formatted seconds)
- Tasks completed
- Tasks in progress
- Last activity timestamp

**Status Colors:**
- active: green
- idle: yellow
- error: red
- stopped: gray

**Health Colors:**
- healthy: green
- warning: yellow
- critical: red

## Implementation Requirements

Create `components/dashboard/agent_status_monitor.py`:

```python
import streamlit as st
from datetime import datetime, timedelta
from lib.session_state import get_state
from lib.mock_data import generate_agent_statuses

def render():
    """Render agent status monitor with health cards."""

    st.subheader("🤖 Agent Status Monitor")

    # Get agent statuses
    agents = get_state('agents', [])

    if not agents:
        agents = generate_agent_statuses()
        st.session_state.agents = agents

    # Scrollable container
    with st.container(height=500, border=True):
        if len(agents) == 0:
            st.caption("No agents active")
        else:
            for agent in agents:
                render_agent_card(agent)

def render_agent_card(agent):
    """Render a single agent status card."""
    name = agent.get('name', 'Unknown Agent')
    icon = agent.get('icon', '🤖')
    status = agent.get('status', 'unknown')
    health = agent.get('health', 'unknown')
    cpu = agent.get('cpu_usage', 0)
    memory = agent.get('memory_usage', 0)
    uptime = agent.get('uptime', 0)
    tasks_completed = agent.get('tasks_completed', 0)
    tasks_in_progress = agent.get('tasks_in_progress', 0)
    last_activity = agent.get('last_activity', 0)

    # Status colors
    status_colors = {
        'active': '#5FAF87',
        'idle': '#F1FA8C',
        'error': '#FF5555',
        'stopped': '#888888'
    }
    status_color = status_colors.get(status, '#888888')

    # Health colors
    health_colors = {
        'healthy': '#5FAF87',
        'warning': '#F1FA8C',
        'critical': '#FF5555'
    }
    health_color = health_colors.get(health, '#888888')

    # Format values
    memory_mb = memory / 1_000_000
    uptime_str = format_uptime(uptime)
    last_activity_str = format_time_ago(last_activity)

    # Render card
    st.markdown(f"""
    <div style="background: rgba(93, 175, 135, 0.05); padding: 1rem; margin-bottom: 1rem;
                border-radius: 0.5rem; border: 1px solid #2d5f4f;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <div>
                <span style="font-size: 1.2rem;">{icon}</span>
                <span style="font-weight: bold; margin-left: 0.5rem;">{name}</span>
            </div>
            <div style="display: flex; gap: 0.5rem;">
                <span style="background: {status_color}; color: #000; padding: 0.2rem 0.5rem;
                           border-radius: 0.25rem; font-size: 0.8rem; font-weight: bold;">
                    {status.upper()}
                </span>
                <span style="background: {health_color}; color: #000; padding: 0.2rem 0.5rem;
                           border-radius: 0.25rem; font-size: 0.8rem; font-weight: bold;">
                    {health.upper()}
                </span>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.9rem;">
            <div>CPU: <strong>{cpu:.1f}%</strong></div>
            <div>Memory: <strong>{memory_mb:.1f} MB</strong></div>
            <div>Uptime: <strong>{uptime_str}</strong></div>
            <div>Last: <strong>{last_activity_str}</strong></div>
            <div>Completed: <strong>{tasks_completed}</strong></div>
            <div>In Progress: <strong>{tasks_in_progress}</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def format_uptime(seconds):
    """Format uptime in seconds to readable string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        return f"{seconds // 3600}h"
    else:
        return f"{seconds // 86400}d"

def format_time_ago(timestamp):
    """Format timestamp as 'X ago' string."""
    now = datetime.now().timestamp()
    diff = int(now - timestamp)

    if diff < 60:
        return "Just now"
    elif diff < 3600:
        minutes = diff // 60
        return f"{minutes}m ago"
    elif diff < 86400:
        hours = diff // 3600
        return f"{hours}h ago"
    else:
        days = diff // 86400
        return f"{days}d ago"
```

## Requirements

1. **Agent cards**: Display 8 agent status cards
2. **Status badges**: Color-coded status (active/idle/error/stopped)
3. **Health indicators**: Color-coded health (healthy/warning/critical)
4. **Metrics**: CPU, memory, uptime, tasks, last activity
5. **Formatting**: Readable formats for memory (MB), uptime (h/m/s), time ago
6. **Styling**: Matrix green theme with borders and proper spacing
7. **Scrollable**: Container height 500px

## Deliverables

1. `components/dashboard/agent_status_monitor.py` - Complete implementation
2. Helper functions for formatting uptime and time
3. Test with mock agent data

Now implement this component.
