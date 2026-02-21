#!/bin/bash

# Agent 06-12: Analytics charts (similar structure to agent-05)
for i in {06..12}; do
  chart_name=$(case $i in
    06) echo "ResponseTime";;
    07) echo "RequestDistribution";;
    08) echo "ErrorRate";;
    09) echo "ErrorTypes";;
    10) echo "UserActivity";;
    11) echo "FeatureUsage";;
    12) echo "PerformanceMetrics";;
  esac)
  
  cat > agent-${i}-$(echo $chart_name | tr '[:upper:]' '[:lower:]' | sed 's/\([A-Z]\)/-\1/g' | tr -d ' ')-chart.md << EOF
---
name: Agent ${i} - ${chart_name}Chart Component
description: Build ${chart_name} chart component with Plotly
agent_type: streamlit-chart
phase: 3
dependencies: [agent-23, agent-24]
priority: medium
---

# Agent ${i}: ${chart_name}Chart Component

Create \`components/analytics/$(echo $chart_name | tr '[:upper:]' '[:lower:]' | sed 's/\([A-Z]\)/_\L\1/g')_chart.py\` with Plotly visualization matching React component. Use Matrix Green theme (#5FAF87, #87D7AF). Reference STREAMLIT_API_REFERENCE.md for st.plotly_chart documentation.
EOF
  echo "Created agent-${i}"
done

# Agent 18: Analytics page
cat > agent-18-analytics-page.md << 'EOF'
---
name: Agent 18 - Analytics Page Orchestration  
description: Integrate all 8 analytics charts into Analytics page with tabs
agent_type: streamlit-page
phase: 3
dependencies: [agent-05, agent-06, agent-07, agent-08, agent-09, agent-10, agent-11, agent-12]
priority: high
---

# Agent 18: Analytics Page Orchestration

Create `pages/analytics.py` that imports all 8 chart components and displays them in tabs (Overview, Performance, Errors, Usage) with time range selector. Reference React Analytics.tsx layout. Use st.tabs() and st.selectbox() for time range (24h/7d/30d/90d/1y).
EOF
echo "Created agent-18"

# Agent 13-16: Reports components
cat > agent-13-reports-listing.md << 'EOF'
---
name: Agent 13 - Reports Listing Page
description: Build reports listing with search and view/download actions
agent_type: streamlit-page
phase: 4
dependencies: [agent-23, agent-24]
priority: high
---

# Agent 13: Reports Listing Page

Create `pages/reports.py` with API integration to fetch reports list, search/filter UI, and dialog to view report content. Use st.text_input() for search, st.dialog() for viewer, call agent-14 MarkdownViewer.
EOF
echo "Created agent-13"

cat > agent-14-markdown-viewer.md << 'EOF'
---
name: Agent 14 - MarkdownViewer Component
description: Build markdown renderer with syntax highlighting  
agent_type: streamlit-component
phase: 4
dependencies: [agent-23, agent-24]
priority: high
---

# Agent 14: MarkdownViewer Component

Create `components/reports/markdown_viewer.py` using st.markdown(content, unsafe_allow_html=True) with custom CSS for Matrix Green prose styling. Add syntax highlighting for code blocks.
EOF
echo "Created agent-14"

cat > agent-15-table-of-contents.md << 'EOF'
---
name: Agent 15 - TableOfContents Component
description: Build TOC generator from markdown headings
agent_type: streamlit-component
phase: 4
dependencies: [agent-14]
priority: medium
---

# Agent 15: TableOfContents Component

Create `components/reports/table_of_contents.py` that extracts h1-h6 from markdown and generates sidebar TOC with anchor links. Use regex to find headings, generate slugs.
EOF
echo "Created agent-15"

cat > agent-16-pdf-export.md << 'EOF'
---
name: Agent 16 - PDF Export Utilities
description: Build PDF export functionality for reports
agent_type: streamlit-utility
phase: 4
dependencies: [agent-14]
priority: low
---

# Agent 16: PDF Export Utilities

Create `components/reports/pdf_export.py` with st.download_button() to export markdown as PDF. Use reportlab or markdown-pdf library. Add word count and read time utilities.
EOF
echo "Created agent-16"

# Agent 19: Analyze page
cat > agent-19-analyze-page.md << 'EOF'
---
name: Agent 19 - Analyze Page
description: Build analysis configuration form page
agent_type: streamlit-page
phase: 5
dependencies: [agent-23, agent-24]
priority: low
---

# Agent 19: Analyze Page

Create `pages/analyze.py` with form for analysis configuration. Use st.form(), st.text_input() for data source, st.selectbox() for analysis type (Full Analysis/Quick Scan/Deep Dive/Custom) and output format (Markdown/JSON/PDF). Add Run/Cancel buttons.
EOF
echo "Created agent-19"

echo "All remaining agent files created successfully!"
