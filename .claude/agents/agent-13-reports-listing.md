---
name: Agent 13 - Reports Listing Page
description: Build reports listing with search and view/download actions
agent_type: streamlit-page
phase: 4
dependencies: [agent-23, agent-24]
priority: high
---

# Agent 13: Reports Listing Page

Create `pages/reports.py` with API integration, search/filter, and report viewer dialog.

## Official Streamlit Documentation

### st.dialog
```python
@st.dialog("Report Viewer")
def view_report(filename):
    content = api.get_report_content(filename)
    st.markdown(content)
```

### st.text_input
```python
search = st.text_input("Search reports", placeholder="Enter search term...")
```

## Implementation

```python
import streamlit as st
from lib.api_client import api
from components.reports.markdown_viewer import render as render_markdown

@st.dialog("Report Viewer", width="large")
def view_report_dialog(filename):
    content = api.get_report_content(filename)
    render_markdown(content)

def render():
    st.title("📄 Reports")
    
    # Search
    search = st.text_input("Search reports", placeholder="Filter by name...")
    
    # Fetch reports
    reports = api.get_reports()
    
    # Filter
    if search:
        reports = [r for r in reports if search.lower() in r['name'].lower()]
    
    # Grid
    cols = st.columns(2)
    for i, report in enumerate(reports):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{report['name']}**")
                st.caption(f"{report['size']} bytes · {report['modified']}")
                if st.button("View", key=f"view_{i}"):
                    view_report_dialog(report['name'])
```

Now implement this page.
