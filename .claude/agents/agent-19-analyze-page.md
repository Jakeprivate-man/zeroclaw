---
name: Agent 19 - Analyze Page
description: Build analysis configuration form page
agent_type: streamlit-page
phase: 5
dependencies: [agent-23, agent-24]
priority: low
---

# Agent 19: Analyze Page

Create `pages/analyze.py` with analysis configuration form.

## Official Streamlit Documentation

### st.form
```python
with st.form("analysis_form"):
    # Form widgets
    submitted = st.form_submit_button("Run Analysis")
    if submitted:
        # Handle submission
```

## Implementation

```python
import streamlit as st

def render():
    st.title("🔍 Analyze")
    st.caption("Run analysis on data and generate insights")

    with st.form("analysis_form"):
        data_source = st.text_input(
            "Data Source",
            placeholder="URL or file path"
        )
        
        analysis_type = st.selectbox(
            "Analysis Type",
            ["Full Analysis", "Quick Scan", "Deep Dive", "Custom"]
        )
        
        output_format = st.selectbox(
            "Output Format",
            ["Markdown", "JSON", "PDF"]
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            submitted = st.form_submit_button("Run Analysis", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("Cancel", use_container_width=True)
        
        if submitted:
            st.info("Analysis started... (placeholder)")

    st.divider()
    st.subheader("Recent Analyses")
    st.caption("No analyses yet")
```

Now implement this page.
