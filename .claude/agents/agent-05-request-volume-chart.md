---
name: Agent 05 - RequestVolumeChart Component
description: Build request volume line chart with successful/failed breakdown
agent_type: streamlit-chart
phase: 3
dependencies: [agent-23, agent-24]
priority: medium
---

# Agent 05: RequestVolumeChart Component

## Task Overview
Create a request volume chart showing successful vs failed requests over time using Plotly.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Official Streamlit Documentation

### st.plotly_chart
```python
st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
```
Display an interactive Plotly chart.

## Implementation Requirements

Create `components/analytics/request_volume_chart.py`:

```python
import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_request_volume_data

def render():
    """Render request volume chart."""
    time_range = get_state('time_range', '7d')
    data = generate_request_volume_data(time_range)

    fig = go.Figure()
    
    # Add successful requests line
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['successful'] for d in data],
        name='Successful',
        line=dict(color='#5FAF87', width=2),
        mode='lines+markers'
    ))
    
    # Add failed requests line
    fig.add_trace(go.Scatter(
        x=[d['date'] for d in data],
        y=[d['failed'] for d in data],
        name='Failed',
        line=dict(color='#FF5555', width=2),
        mode='lines+markers'
    ))

    # Update layout
    fig.update_layout(
        title="Request Volume Over Time",
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF"),
        xaxis_title="Date",
        yaxis_title="Requests",
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)
```

## Requirements
1. Plotly line chart with 2 series (successful, failed)
2. Matrix green theme colors
3. Responsive width
4. Interactive hover tooltips

Now implement this chart component.
