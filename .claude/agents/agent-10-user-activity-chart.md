---
name: Agent 10 - UserActivityChart Component
description: User activity area chart (active/new users)
agent_type: streamlit-chart
phase: 3
dependencies: [agent-23, agent-24]
priority: medium
---

# Agent 10: UserActivityChart Component

## Task Overview
Create UserActivityChart component using Plotly for data visualization.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Official Streamlit Documentation

### st.plotly_chart
```python
st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
```
Display an interactive Plotly chart.

**Parameters:**
- `fig`: Plotly figure object
- `use_container_width`: Expand to container width
- `config`: Chart configuration dict

## Implementation Requirements

Create `components/analytics/LUser_LActivity_LChart.py`:

```python
import streamlit as st
import plotly.graph_objects as go
from lib.session_state import get_state
from lib.mock_data import generate_LUser_LActivity_data

def render():
    """Render UserActivityChart."""
    time_range = get_state('time_range', '7d')
    data = generate_LUser_LActivity_data(time_range)

    fig = go.Figure()
    
    # Add chart traces here based on data structure
    # Use Matrix Green theme colors: #5FAF87, #87D7AF
    # Red for errors: #FF5555, Yellow for warnings: #F1FA8C
    
    fig.update_layout(
        title="User activity area chart (active/new users)",
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#87D7AF"),
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)
```

## Requirements
1. Plotly chart matching React component design
2. Matrix Green theme colors
3. Responsive width (`use_container_width=True`)
4. Interactive hover tooltips
5. Height: 400px

## Deliverables
1. `components/analytics/LUser_LActivity_LChart.py` - Complete implementation
2. Integration with mock data generator
3. Reference React component for data structure

Now implement this chart component.
