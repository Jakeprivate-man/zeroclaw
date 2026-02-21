"""Reports Components Package.

This package contains all components for the Reports page functionality:
- ReportsListing: Main page with search and grid display
- MarkdownViewer: Matrix Green themed markdown renderer
- TableOfContents: TOC generator from markdown headings
- PDF Export: Download and export utilities

All components share the Matrix Green theme (#5FAF87, #87D7AF, #000000 bg).
"""

from components.reports.reports_listing import render as render_reports_listing
from components.reports.markdown_viewer import render as render_markdown
from components.reports.table_of_contents import render as render_toc
from components.reports.pdf_export import export_pdf

__all__ = [
    'render_reports_listing',
    'render_markdown',
    'render_toc',
    'export_pdf',
]
