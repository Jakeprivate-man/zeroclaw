"""TableOfContents Component - Extract and display markdown headings.

This component generates a table of contents from markdown content
by extracting headings and creating navigation links.
"""

import re
import streamlit as st


def render(content: str):
    """Generate TOC from markdown headings.

    Extracts all markdown headings (# through ######) and displays them
    as a hierarchical table of contents with indentation.

    Args:
        content: Raw markdown content to extract headings from
    """

    # Extract headings using regex
    # Pattern matches: one or more #, followed by space, then heading text
    headings = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)

    if not headings:
        st.info("No headings found in this document")
        return

    # Custom CSS for TOC styling with Matrix Green theme
    st.markdown("""
    <style>
    .toc-heading {
        color: #5FAF87;
        font-weight: bold;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
    }
    .toc-item {
        color: #87D7AF;
        margin: 0.25rem 0;
    }
    .toc-item a {
        color: #87D7AF;
        text-decoration: none;
    }
    .toc-item a:hover {
        color: #5FAF87;
        text-decoration: underline;
    }
    </style>
    """, unsafe_allow_html=True)

    # Display TOC heading
    st.markdown('<div class="toc-heading">Table of Contents</div>', unsafe_allow_html=True)

    # Render each heading with appropriate indentation
    for level_marks, text in headings:
        # Calculate indentation based on heading level (h1=0, h2=1, etc.)
        level = len(level_marks) - 1
        indent = "&nbsp;" * level * 4

        # Create URL-safe slug from heading text
        # Convert to lowercase, replace spaces with hyphens, remove special chars
        slug = text.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)

        # Render TOC item with indentation and link
        st.markdown(
            f'<div class="toc-item">{indent}• <a href="#{slug}">{text}</a></div>',
            unsafe_allow_html=True
        )
