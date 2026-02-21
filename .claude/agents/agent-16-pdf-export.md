---
name: Agent 16 - PDF Export Utilities
description: Build PDF export functionality for reports
agent_type: streamlit-utility
phase: 4
dependencies: [agent-14]
priority: low
---

# Agent 16: PDF Export Utilities

Create `components/reports/pdf_export.py` with download button.

## Official Streamlit Documentation

### st.download_button
```python
st.download_button("Download PDF", pdf_bytes, "report.pdf", "application/pdf")
```

## Implementation

```python
import streamlit as st

def export_pdf(content, filename):
    """Export markdown as PDF."""
    
    # Word count
    word_count = len(content.split())
    read_time = word_count // 200
    
    st.caption(f"{word_count:,} words · {read_time} min read")
    
    # For now, just export as text
    # TODO: Use reportlab or weasyprint for actual PDF
    if st.button("Download as Text"):
        st.download_button(
            "Download",
            content.encode('utf-8'),
            f"{filename}.txt",
            "text/plain"
        )
```

Now implement this utility.
