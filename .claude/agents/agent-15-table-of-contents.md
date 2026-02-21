---
name: Agent 15 - TableOfContents Component
description: Build TOC generator from markdown headings
agent_type: streamlit-component
phase: 4
dependencies: [agent-14]
priority: medium
---

# Agent 15: TableOfContents Component

Create `components/reports/table_of_contents.py` extracting headings with regex.

## Implementation

```python
import re
import streamlit as st

def render(content):
    """Generate TOC from markdown headings."""
    
    # Extract headings
    headings = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
    
    st.markdown("### Table of Contents")
    for level, text in headings:
        indent = "&nbsp;" * (len(level) - 1) * 4
        slug = text.lower().replace(' ', '-')
        st.markdown(f"{indent}• [{text}](#{slug})", unsafe_allow_html=True)
```

Now implement this component.
