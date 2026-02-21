---
name: Agent 01 - RealTimeMetrics Component
description: Build RealTimeMetrics component with 4 metric cards and sparklines
agent_type: streamlit-component
phase: 2
dependencies: [agent-23, agent-24]
priority: high
---

# Agent 01: RealTimeMetrics Component

## Task Overview
Create the RealTimeMetrics component that displays 4 metric cards with live updates and sparkline charts.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Official Streamlit Documentation

### st.metric
Display a metric in big bold font with optional delta indicator.

```python
st.metric(label, value, delta=None, delta_color="normal", help=None,
          label_visibility="visible", border=False)
```

**Parameters:**
- `label` (str): Metric name
- `value` (str/int/float): Metric value
- `delta` (str/int/float/None): Change indicator
- `delta_color` ("normal"/"inverse"/"off"): Color interpretation

**Example:**
```python
st.metric("Temperature", "70 °F", "1.2 °F")
```

### st.columns
Create side-by-side columns.

```python
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Metric 1", value)
```

## Context: React RealTimeMetrics Component

The React version (`web-ui/src/components/dashboard/RealTimeMetrics.tsx`) displays:

1. **Active Agents** - Count with trend and sparkline
2. **Requests Today** - Count with trend and sparkline
3. **CPU Usage** - Percentage with sparkline (color-coded)
4. **Reports Generated** - Count with trend and sparkline

**Real-time behavior:**
- Updates every 2 seconds via `gatewayStore.startRealTimeUpdates()`
- Sparklines show last 20 data points
- Trends show up/down indicators (↑/↓)

## Implementation Requirements

Create `components/dashboard/real_time_metrics.py`:

```python
import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state, update_gateway_state
from lib.mock_data import generate_gateway_stats

def render():
    """Render 4 real-time metric cards with sparklines."""

    # Get current stats
    stats = get_state('gateway_stats')
    metrics_history = get_state('metrics_history', {})
    cpu_usage = get_state('cpu_usage', 0)

    # Update stats (simulated real-time)
    if stats is None:
        stats = generate_gateway_stats()
        update_gateway_state(stats=stats)

    # Create 4-column layout
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Active Agents metric with sparkline
        active_agents = stats.get('active_agents', 0)
        trend = calculate_trend(metrics_history.get('active_agents', []))

        st.metric(
            "Active Agents",
            active_agents,
            delta=f"{trend:+.1f}%" if trend != 0 else None,
            delta_color="normal"
        )
        render_sparkline(metrics_history.get('active_agents', []), "#5FAF87")

    with col2:
        # Requests Today metric
        requests = stats.get('requests_today', 0)
        trend = calculate_trend(metrics_history.get('requests_today', []))

        st.metric(
            "Requests Today",
            f"{requests:,}",
            delta=f"{trend:+.1f}%" if trend != 0 else None
        )
        render_sparkline(metrics_history.get('requests_today', []), "#87D7AF")

    with col3:
        # CPU Usage metric (color-coded)
        delta_color = "inverse" if cpu_usage > 80 else "normal"

        st.metric(
            "CPU Usage",
            f"{cpu_usage:.0f}%",
            delta=None,
            delta_color=delta_color
        )

        # Color based on threshold
        color = "#FF5555" if cpu_usage > 80 else "#F1FA8C" if cpu_usage > 60 else "#5FAF87"
        render_sparkline(metrics_history.get('cpu_usage', []), color)

    with col4:
        # Reports Generated metric
        reports = stats.get('reports_generated', 0)
        trend = calculate_trend(metrics_history.get('reports_generated', []))

        st.metric(
            "Reports Generated",
            reports,
            delta=f"{trend:+.1f}%" if trend != 0 else None
        )
        render_sparkline(metrics_history.get('reports_generated', []), "#5FAF87")

def calculate_trend(history):
    """Calculate percentage trend from history."""
    if not history or len(history) < 2:
        return 0
    recent = history[-3:]  # Last 3 points
    if len(recent) < 2:
        return 0
    old_avg = sum(h['value'] for h in recent[:-1]) / (len(recent) - 1)
    new_val = recent[-1]['value']
    if old_avg == 0:
        return 0
    return ((new_val - old_avg) / old_avg) * 100

def render_sparkline(history, color):
    """Render a mini sparkline chart using Plotly."""
    if not history or len(history) == 0:
        return

    values = [h['value'] for h in history[-20:]]  # Last 20 points

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=values,
        mode='lines',
        line=dict(color=color, width=2),
        showlegend=False,
        hoverinfo='skip'
    ))

    fig.update_layout(
        height=60,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode=False
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
```

## Requirements

1. **4 metrics**: Active Agents, Requests Today, CPU Usage, Reports Generated
2. **Sparklines**: Plotly mini-charts (96px wide, 48px tall equivalent)
3. **Trends**: Calculate percentage change from recent history
4. **Color-coding**: CPU usage red if >80%, yellow if >60%, green otherwise
5. **Real-time updates**: Read from session state (updated by app.py timer)

## Deliverables

1. `components/dashboard/real_time_metrics.py` - Complete implementation
2. Helper functions for trend calculation and sparkline rendering
3. Test with mock data

## Testing

```python
# In app.py or test file
from components.dashboard.real_time_metrics import render as render_metrics

render_metrics()
```

Now implement this component.
