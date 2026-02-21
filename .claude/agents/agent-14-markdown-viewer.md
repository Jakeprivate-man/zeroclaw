---
name: Agent 14 - MarkdownViewer Component
description: Build markdown renderer with syntax highlighting
agent_type: streamlit-component
phase: 4
dependencies: [agent-23, agent-24]
priority: high
---

# Agent 14: MarkdownViewer Component

Create `components/reports/markdown_viewer.py` with Matrix Green prose styling.

## Implementation

```python
import streamlit as st

def render(content):
    """Render markdown with custom Matrix Green styling."""
    
    # Custom CSS
    st.markdown("""
    <style>
    .markdown-body {
        color: #87D7AF;
    }
    .markdown-body h1, .markdown-body h2, .markdown-body h3 {
        color: #5FAF87;
        font-weight: bold;
    }
    .markdown-body code {
        background: #1a1a1a;
        padding: 0.2rem 0.4rem;
        border-radius: 0.25rem;
    }
    .markdown-body pre {
        background: #1a1a1a;
        padding: 1rem;
        border-radius: 0.5rem;
        overflow-x: auto;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Render markdown
    st.markdown(content, unsafe_allow_html=True)
```

Now implement this component.
