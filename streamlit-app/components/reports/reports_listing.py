"""ReportsListing Component - Main reports page with search and viewer.

This component provides the main reports listing interface with:
- Search/filter functionality
- Grid layout display
- Report viewer dialog integration
- API integration for fetching reports
"""

import streamlit as st
from lib.api_client import api
from components.reports.markdown_viewer import render as render_markdown
from components.reports.table_of_contents import render as render_toc
from components.reports.pdf_export import export_pdf


@st.dialog("Report Viewer", width="large")
def view_report_dialog(filename: str):
    """Display report in a dialog with TOC and export options.

    Args:
        filename: Report filename to display
    """
    try:
        # Fetch report content from API
        content = api.get_report_content(filename)

        # Create layout with sidebar for TOC and main content area
        col1, col2 = st.columns([1, 3])

        with col1:
            # Table of contents in left column
            render_toc(content)
            st.divider()
            # Export options below TOC
            export_pdf(content, filename)

        with col2:
            # Main report content in right column
            render_markdown(content)

    except FileNotFoundError:
        st.error(f"Report not found: {filename}")
    except ConnectionError as e:
        st.error(f"Connection error: {str(e)}")
    except Exception as e:
        st.error(f"Error loading report: {str(e)}")


def render():
    """Render the main reports listing page.

    Displays search bar, fetches reports from API, and shows them
    in a responsive grid layout with view buttons.
    """

    # Page title with Matrix Green styling
    st.markdown("""
    <style>
    .reports-title {
        color: #5FAF87;
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .report-card {
        border: 1px solid #5FAF87;
        border-radius: 0.5rem;
        padding: 1rem;
        background: #0a0a0a;
    }
    .report-name {
        color: #5FAF87;
        font-weight: bold;
        font-size: 1.1rem;
    }
    .report-meta {
        color: #87D7AF;
        font-size: 0.85rem;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="reports-title">📄 Reports</div>', unsafe_allow_html=True)

    # Search input
    search = st.text_input(
        "Search reports",
        placeholder="Filter by name...",
        label_visibility="collapsed"
    )

    try:
        # Fetch reports from API
        reports = api.get_reports()

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            reports = [r for r in reports if search_lower in r['name'].lower()]

        # Display count
        st.caption(f"Found {len(reports)} report(s)")

        if not reports:
            st.info("No reports found")
            return

        # Display reports in 2-column grid
        cols = st.columns(2)
        for i, report in enumerate(reports):
            with cols[i % 2]:
                with st.container(border=True):
                    # Report name
                    st.markdown(f"**{report['name']}**")

                    # Metadata
                    size_kb = report.get('size', 0) / 1024
                    modified = report.get('modified', 'Unknown')
                    st.caption(f"{size_kb:.1f} KB · {modified}")

                    # View button
                    if st.button("View", key=f"view_{i}", use_container_width=True):
                        view_report_dialog(report['name'])

    except ConnectionError as e:
        st.error(f"Could not connect to ZeroClaw gateway: {str(e)}")
        st.info("Make sure the ZeroClaw gateway is running at http://localhost:3000")
    except Exception as e:
        st.error(f"Error loading reports: {str(e)}")
