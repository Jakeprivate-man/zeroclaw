"""MarkdownViewer Component - Matrix Green Theme Renderer.

This component renders markdown content with custom Matrix Green styling
optimized for reports viewing.
"""

import streamlit as st


def render(content: str):
    """Render markdown with custom Matrix Green styling.

    Args:
        content: Raw markdown content to render
    """

    # Custom CSS for Matrix Green theme
    st.markdown("""
    <style>
    .markdown-body {
        color: #87D7AF;
        line-height: 1.6;
    }
    .markdown-body h1, .markdown-body h2, .markdown-body h3 {
        color: #5FAF87;
        font-weight: bold;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    .markdown-body h1 {
        font-size: 2rem;
        border-bottom: 2px solid #5FAF87;
        padding-bottom: 0.5rem;
    }
    .markdown-body h2 {
        font-size: 1.5rem;
        border-bottom: 1px solid #5FAF87;
        padding-bottom: 0.3rem;
    }
    .markdown-body h3 {
        font-size: 1.25rem;
    }
    .markdown-body code {
        background: #1a1a1a;
        color: #87D7AF;
        padding: 0.2rem 0.4rem;
        border-radius: 0.25rem;
        font-family: 'Courier New', monospace;
    }
    .markdown-body pre {
        background: #1a1a1a;
        padding: 1rem;
        border-radius: 0.5rem;
        overflow-x: auto;
        border: 1px solid #5FAF87;
    }
    .markdown-body pre code {
        background: transparent;
        padding: 0;
    }
    .markdown-body blockquote {
        border-left: 4px solid #5FAF87;
        padding-left: 1rem;
        margin-left: 0;
        color: #87D7AF;
        font-style: italic;
    }
    .markdown-body a {
        color: #5FAF87;
        text-decoration: none;
    }
    .markdown-body a:hover {
        text-decoration: underline;
    }
    .markdown-body table {
        border-collapse: collapse;
        width: 100%;
        margin: 1rem 0;
    }
    .markdown-body th, .markdown-body td {
        border: 1px solid #5FAF87;
        padding: 0.5rem;
        text-align: left;
    }
    .markdown-body th {
        background: #1a1a1a;
        color: #5FAF87;
        font-weight: bold;
    }
    .markdown-body ul, .markdown-body ol {
        padding-left: 2rem;
    }
    .markdown-body li {
        margin: 0.25rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # Render markdown with custom styling applied
    st.markdown(f'<div class="markdown-body">{content}</div>', unsafe_allow_html=True)
