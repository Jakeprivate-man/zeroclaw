"""Test script for the Settings page.

This script demonstrates the Settings page functionality in isolation.
Run with: streamlit run test_settings.py
"""

import streamlit as st
from lib.session_state import initialize_session_state
from pages import settings

# Initialize session state
initialize_session_state()

# Set page config
st.set_page_config(
    page_title="Settings Test - ZeroClaw",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply matrix green theme
st.markdown("""
<style>
    /* Matrix green theme */
    :root {
        --primary-color: #5FAF87;
        --secondary-color: #87D7AF;
        --background-color: #000000;
        --text-color: #87D7AF;
    }

    /* Main background */
    .stApp {
        background-color: #000000;
    }

    /* Text colors */
    .stMarkdown, .stText {
        color: #87D7AF !important;
    }

    /* Headers */
    h1, h2, h3 {
        color: #5FAF87 !important;
    }

    /* Success/error messages */
    .stSuccess {
        background-color: #1a3d2e;
        color: #5FAF87;
    }

    .stError {
        background-color: #3d1a1a;
        color: #FF5555;
    }

    .stInfo {
        background-color: #1a2d3d;
        color: #87D7AF;
    }

    .stWarning {
        background-color: #3d3a1a;
        color: #F1FA8C;
    }

    /* Inputs */
    .stTextInput input {
        background-color: #0d0d0d;
        color: #87D7AF;
        border: 1px solid #2d5f4f;
    }

    /* Buttons */
    .stButton button {
        background-color: #1a3d2e;
        color: #5FAF87;
        border: 1px solid #2d5f4f;
    }

    .stButton button:hover {
        background-color: #2d5f4f;
        border-color: #5FAF87;
    }

    /* Checkboxes */
    .stCheckbox {
        color: #87D7AF;
    }

    /* Selectbox */
    .stSelectbox select {
        background-color: #0d0d0d;
        color: #87D7AF;
        border: 1px solid #2d5f4f;
    }

    /* Dividers */
    hr {
        border-color: #2d5f4f;
    }

    /* Code blocks */
    .stCodeBlock {
        background-color: #0d0d0d;
        border: 1px solid #2d5f4f;
    }

    /* JSON viewer */
    .stJson {
        background-color: #0d0d0d;
        color: #87D7AF;
    }
</style>
""", unsafe_allow_html=True)

# Render the settings page
settings.render()

# Show footer
st.divider()
st.caption("ZeroClaw Streamlit UI - Settings Test")
