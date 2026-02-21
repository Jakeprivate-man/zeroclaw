"""
ZeroClaw Streamlit UI - Main Application Entry Point

This is the root application file that handles:
- Page configuration (MUST be first Streamlit command)
- Session state initialization
- Matrix Green theme CSS
- Page routing
- Component integration
"""

import streamlit as st

# Core library imports
from lib.session_state import initialize_session_state
from components.sidebar import render_sidebar

# Page imports with graceful fallback
try:
    from pages import dashboard, chat, analytics, reports, analyze, settings
except ImportError:
    # Graceful degradation if pages don't exist yet
    dashboard = chat = analytics = reports = analyze = settings = None

# =============================================================================
# PAGE CONFIG - MUST BE FIRST STREAMLIT COMMAND
# =============================================================================

st.set_page_config(
    page_title="ZeroClaw UI",
    page_icon="🦀",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/zeroclaw/zeroclaw',
        'About': """
        # ZeroClaw Web UI

        Real-time monitoring and analytics for ZeroClaw agent runtime.

        Built with Streamlit | Matrix Green Theme
        """
    }
)

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

initialize_session_state()

# =============================================================================
# MATRIX GREEN THEME CSS
# =============================================================================

st.markdown("""
<style>
    /* Matrix Green Theme */
    :root {
        --background-color: #000000;
        --foreground-color: #87D7AF;
        --primary-color: #5FAF87;
        --secondary-color: #2d5f4f;
        --border-color: #2d5f4f;
        --accent-color: #87D7AF;
    }

    /* Main background */
    .stApp {
        background-color: var(--background-color);
        color: var(--foreground-color);
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: var(--background-color);
        border-right: 1px solid var(--border-color);
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: var(--foreground-color);
    }

    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: var(--primary-color) !important;
        font-family: 'Courier New', monospace;
    }

    /* Text elements */
    p, span, div, label {
        color: var(--foreground-color);
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: rgba(93, 175, 135, 0.1);
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid var(--border-color);
    }

    [data-testid="stMetricLabel"] {
        color: var(--accent-color) !important;
    }

    [data-testid="stMetricValue"] {
        color: var(--primary-color) !important;
    }

    /* Buttons */
    .stButton > button {
        border: 1px solid var(--primary-color);
        color: var(--primary-color);
        background-color: transparent;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        background-color: var(--primary-color);
        color: var(--background-color);
        border-color: var(--accent-color);
    }

    /* Input fields */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea {
        background-color: rgba(93, 175, 135, 0.05);
        border: 1px solid var(--border-color);
        color: var(--foreground-color);
    }

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 1px var(--primary-color);
    }

    /* Select boxes */
    .stSelectbox > div > div {
        background-color: rgba(93, 175, 135, 0.05);
        border: 1px solid var(--border-color);
    }

    /* Data frames and tables */
    .stDataFrame {
        border: 1px solid var(--border-color);
    }

    /* Code blocks */
    .stCodeBlock {
        background-color: rgba(93, 175, 135, 0.05);
        border: 1px solid var(--border-color);
    }

    code {
        color: var(--accent-color);
        background-color: rgba(93, 175, 135, 0.1);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border: 1px solid var(--border-color);
        color: var(--foreground-color);
    }

    .stTabs [aria-selected="true"] {
        background-color: rgba(93, 175, 135, 0.2);
        border-color: var(--primary-color);
        color: var(--primary-color);
    }

    /* Expander */
    .streamlit-expanderHeader {
        background-color: rgba(93, 175, 135, 0.05);
        border: 1px solid var(--border-color);
        color: var(--foreground-color);
    }

    .streamlit-expanderHeader:hover {
        border-color: var(--primary-color);
    }

    /* Success/Info/Warning/Error boxes */
    .stSuccess {
        background-color: rgba(93, 175, 135, 0.1);
        border-left: 4px solid var(--primary-color);
        color: var(--foreground-color);
    }

    .stInfo {
        background-color: rgba(135, 215, 175, 0.1);
        border-left: 4px solid var(--accent-color);
        color: var(--foreground-color);
    }

    .stWarning {
        background-color: rgba(241, 250, 140, 0.1);
        border-left: 4px solid #F1FA8C;
        color: var(--foreground-color);
    }

    .stError {
        background-color: rgba(255, 85, 85, 0.1);
        border-left: 4px solid #FF5555;
        color: var(--foreground-color);
    }

    /* Dividers */
    hr {
        border-color: var(--border-color);
    }

    /* Links */
    a {
        color: var(--accent-color);
    }

    a:hover {
        color: var(--primary-color);
    }

    /* Spinner */
    .stSpinner > div {
        border-top-color: var(--primary-color);
    }

    /* Progress bar */
    .stProgress > div > div > div {
        background-color: var(--primary-color);
    }

    /* Radio buttons */
    .stRadio > label {
        color: var(--foreground-color);
    }

    /* Checkboxes */
    .stCheckbox > label {
        color: var(--foreground-color);
    }

    /* Slider */
    .stSlider > div > div > div {
        background-color: var(--border-color);
    }

    .stSlider > div > div > div > div {
        background-color: var(--primary-color);
    }

    /* File uploader */
    .stFileUploader > div {
        background-color: rgba(93, 175, 135, 0.05);
        border: 1px dashed var(--border-color);
    }

    /* Download button */
    .stDownloadButton > button {
        border: 1px solid var(--primary-color);
        color: var(--primary-color);
        background-color: transparent;
    }

    .stDownloadButton > button:hover {
        background-color: var(--primary-color);
        color: var(--background-color);
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SIDEBAR AND NAVIGATION
# =============================================================================

# Render sidebar and get selected page
selected_page = render_sidebar()

# =============================================================================
# PAGE ROUTING
# =============================================================================

if selected_page == "Dashboard":
    if dashboard:
        dashboard.render()
    else:
        st.title("📊 Dashboard")
        st.info("Dashboard page is under construction by Agent 17")
        st.markdown("""
        The Dashboard will display:
        - Real-time agent status
        - Performance metrics
        - System health indicators
        - Quick action buttons
        """)

elif selected_page == "Chat":
    if chat:
        chat.render()
    else:
        st.title("💬 Chat")
        st.info("Chat page is under construction")
        st.markdown("""
        The Chat page will provide:
        - Real-time messaging with ZeroClaw agent
        - Conversation history
        - Message persistence
        - Model selection
        """)

elif selected_page == "Analytics":
    if analytics:
        analytics.render()
    else:
        st.title("📈 Analytics")
        st.info("Analytics page is under construction by Agent 18")
        st.markdown("""
        The Analytics page will provide:
        - Historical performance trends
        - Token usage analytics
        - Cost tracking
        - Model comparison charts
        """)

elif selected_page == "Reports":
    if reports:
        reports.render()
    else:
        st.title("📄 Reports")
        st.info("Reports page is under construction by Agent 13")
        st.markdown("""
        The Reports page will feature:
        - Conversation logs
        - Agent activity reports
        - Export capabilities
        - Search and filter options
        """)

elif selected_page == "Analyze":
    if analyze:
        analyze.render()
    else:
        st.title("🔍 Analyze")
        st.info("Analyze page is under construction by Agent 19")
        st.markdown("""
        The Analyze page will enable:
        - Deep conversation analysis
        - Performance diagnostics
        - Failure pattern detection
        - Optimization recommendations
        """)

elif selected_page == "Settings":
    if settings:
        settings.render()
    else:
        st.title("⚙️ Settings")
        st.info("Settings page is under construction by Agent 21")
        st.markdown("""
        The Settings page will allow:
        - API endpoint configuration
        - Theme customization
        - Notification preferences
        - Data retention settings
        """)

else:
    # Fallback for unknown page
    st.error(f"Unknown page: {selected_page}")
    st.info("Please select a valid page from the sidebar.")

# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.caption("ZeroClaw Web UI | Built with Streamlit | Matrix Green Theme")
