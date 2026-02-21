---
name: Agent 18 - Analytics Page Orchestration
description: Integrate all 8 analytics charts into Analytics page with tabs
agent_type: streamlit-page
phase: 3
dependencies: [agent-05, agent-06, agent-07, agent-08, agent-09, agent-10, agent-11, agent-12]
priority: high
---

# Agent 18: Analytics Page Orchestration

Create `pages/analytics.py` integrating all 8 chart components with tabs and time range selector.

## Official Streamlit Documentation

### st.tabs
```python
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Performance", "Errors", "Usage"])
with tab1:
    # Tab content
```

### st.metric
```python
st.metric("Total Requests", "12,543", delta="8.2%")
```

## Implementation

```python
import streamlit as st
from components.analytics import (
    request_volume_chart, response_time_chart, request_distribution_chart,
    error_rate_chart, error_types_chart, user_activity_chart,
    feature_usage_chart, performance_metrics_chart
)

def render():
    st.title("📈 Analytics")
    st.caption("Monitor performance metrics and insights over time")

    # Time range selector
    col1, col2 = st.columns([3, 1])
    with col1:
        time_range = st.selectbox("Time Range", ["24h", "7d", "30d", "90d", "1y"], index=1)
        st.session_state.time_range = time_range
    with col2:
        st.button("Export", disabled=True)  # Placeholder

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Requests", "12,543", delta="8.2%")
    with col2:
        st.metric("Avg Response", "234ms", delta="-12ms")
    with col3:
        st.metric("Error Rate", "2.1%", delta="-0.3%", delta_color="inverse")
    with col4:
        st.metric("Active Users", "1,234", delta="45")

    st.divider()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Performance", "Errors", "Usage"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            request_volume_chart.render()
        with col2:
            request_distribution_chart.render()

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            response_time_chart.render()
        with col2:
            performance_metrics_chart.render()

    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            error_rate_chart.render()
        with col2:
            error_types_chart.render()

    with tab4:
        col1, col2 = st.columns(2)
        with col1:
            user_activity_chart.render()
        with col2:
            feature_usage_chart.render()
```

Now implement this page.
