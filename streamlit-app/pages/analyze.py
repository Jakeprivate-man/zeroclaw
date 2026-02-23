"""
Analyze Page - Analysis configuration form page.

This page provides a form for configuring and running data analysis tasks.
"""

import streamlit as st
from lib.session_state import add_activity


def render():
    """
    Render the Analyze page with configuration form.

    Displays:
    - Analysis configuration form
    - Data source input
    - Analysis type selector
    - Output format selector
    - Submit and cancel buttons
    - Recent analyses list (placeholder)
    """
    st.title("🔍 Analyze")
    st.caption("Run analysis on data and generate insights")

    # Analysis configuration form
    with st.form("analysis_form"):
        data_source = st.text_input(
            "Data Source",
            placeholder="URL or file path",
            help="Enter the URL or file path of the data to analyze"
        )

        analysis_type = st.selectbox(
            "Analysis Type",
            ["Full Analysis", "Quick Scan", "Deep Dive", "Custom"],
            help="Select the type of analysis to perform"
        )

        output_format = st.selectbox(
            "Output Format",
            ["Markdown", "JSON", "PDF"],
            help="Choose the format for the analysis output"
        )

        # Advanced options (collapsible)
        with st.expander("Advanced Options"):
            include_visualizations = st.checkbox(
                "Include Visualizations",
                value=True,
                help="Generate charts and graphs in the output"
            )

            include_summary = st.checkbox(
                "Include Executive Summary",
                value=True,
                help="Add a summary section at the beginning"
            )

            max_depth = st.slider(
                "Analysis Depth",
                min_value=1,
                max_value=10,
                value=5,
                help="How deep to analyze (1=shallow, 10=comprehensive)"
            )

        # Form buttons
        col1, col2 = st.columns([3, 1])
        with col1:
            submitted = st.form_submit_button(
                "🚀 Run Analysis",
                use_container_width=True,
                type="primary"
            )
        with col2:
            cancel = st.form_submit_button(
                "Cancel",
                use_container_width=True
            )

        # Handle form submission
        if submitted:
            if not data_source:
                st.error("❌ Please provide a data source")
            else:
                st.info(
                    "Analysis submission is not yet connected to the ZeroClaw backend. "
                    "This feature is coming soon."
                )

                # Add activity to stream
                add_activity(
                    activity_type='analysis_started',
                    message=f'Analysis started: {analysis_type} on {data_source}',
                    icon='🔍',
                    metadata={
                        'data_source': data_source,
                        'analysis_type': analysis_type,
                        'output_format': output_format
                    }
                )

        if cancel:
            st.info("Analysis cancelled")

    # Recent analyses section
    st.divider()
    st.subheader("Recent Analyses")
    st.caption("No analyses yet")

    # Placeholder for recent analyses list
    # This could be populated from session state or API in the future
    if st.session_state.get('recent_analyses'):
        for analysis in st.session_state.recent_analyses:
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"**{analysis['type']}**")
                with col2:
                    st.caption(analysis['source'])
                with col3:
                    st.button("View", key=f"view_{analysis['id']}")
    else:
        st.info("No recent analyses. Submit the form above to start your first analysis.")


# Public API
__all__ = ['render']
