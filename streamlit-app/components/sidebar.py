"""
ZeroClaw Streamlit UI - Sidebar Component

Renders the navigation sidebar with real gateway connection status
and ZeroClaw binary detection.
"""

import os
import shutil
import streamlit as st
import requests

ZEROCLAW_BINARY_PATH = os.path.expanduser("~/zeroclaw/target/release/zeroclaw")


def _check_gateway_status(gateway_url: str) -> None:
    """Check gateway health and display status in sidebar.

    Args:
        gateway_url: The gateway URL to check (e.g. http://localhost:3000)
    """
    try:
        r = requests.get(f"{gateway_url}/health", timeout=2)
        if r.ok:
            st.success("Gateway online")
        else:
            st.warning(f"Gateway HTTP {r.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("Gateway offline")
    except requests.exceptions.Timeout:
        st.error("Gateway timeout")
    except Exception:
        st.error("Gateway unreachable")


def _check_binary_status() -> None:
    """Check if the zeroclaw binary exists at the known build path or on PATH."""
    if os.path.isfile(ZEROCLAW_BINARY_PATH) and os.access(ZEROCLAW_BINARY_PATH, os.X_OK):
        st.success("zeroclaw binary found")
    elif shutil.which("zeroclaw"):
        st.success("zeroclaw binary found")
    else:
        st.warning("zeroclaw binary not found")


def render_sidebar() -> str:
    """
    Render the sidebar and return the selected page.

    Returns:
        str: The name of the selected page
    """
    with st.sidebar:
        st.title("ZeroClaw")
        st.caption("Agent Runtime UI")

        st.divider()

        # Navigation menu
        st.subheader("Navigation")

        page = st.radio(
            "Select a page:",
            ["Dashboard", "Chat", "Analytics", "Reports", "Analyze", "Settings"],
            label_visibility="collapsed"
        )

        st.divider()

        # Connection status - real checks
        st.subheader("Status")

        gateway_url = st.session_state.get('gateway_url', 'http://localhost:3000')
        _check_gateway_status(gateway_url)
        _check_binary_status()

        st.divider()

    return page
