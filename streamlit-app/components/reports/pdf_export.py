"""PDF Export Utilities - Download and export functionality for reports.

This component provides export functionality for reports with word count,
read time estimation, and download capabilities.
"""

import streamlit as st


def export_pdf(content: str, filename: str):
    """Export markdown as downloadable file with metadata.

    Displays document statistics (word count, estimated read time) and
    provides download button. Currently exports as text file; can be
    extended to actual PDF generation using reportlab or weasyprint.

    Args:
        content: Markdown content to export
        filename: Original filename (will be used for download)
    """

    # Calculate document statistics
    word_count = len(content.split())
    # Average reading speed: 200 words per minute
    read_time = max(1, word_count // 200)

    # Display metadata in Matrix Green theme
    st.markdown("""
    <style>
    .export-metadata {
        color: #87D7AF;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    .export-metadata strong {
        color: #5FAF87;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        f'<div class="export-metadata">'
        f'<strong>{word_count:,}</strong> words &bull; '
        f'<strong>{read_time}</strong> min read'
        f'</div>',
        unsafe_allow_html=True
    )

    # Create download button
    # Remove .md extension if present, add .txt
    base_filename = filename.replace('.md', '')
    download_filename = f"{base_filename}.txt"

    st.download_button(
        label="Download as Text",
        data=content.encode('utf-8'),
        file_name=download_filename,
        mime="text/plain",
        help="Download this report as a plain text file"
    )

    # TODO: Future enhancement - actual PDF generation
    # Uncomment when reportlab/weasyprint is available:
    #
    # if st.button("Generate PDF", help="Convert to PDF (coming soon)"):
    #     st.info("PDF generation will be available in a future update")
    #     # from reportlab.lib.pagesizes import letter
    #     # from reportlab.platypus import SimpleDocTemplate, Paragraph
    #     # ... generate PDF ...
