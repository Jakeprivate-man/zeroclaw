"""Settings page for configuring the ZeroClaw Streamlit app.

This page provides configuration options for:
- Gateway connection settings
- UI appearance (theme, font size)
- User preferences (debug mode, auto-refresh)
"""

import streamlit as st
import json
import os
from pathlib import Path
from lib.api_client import ZeroClawAPIClient
from lib.session_state import update_settings


# Configuration file path
CONFIG_FILE = Path(__file__).parent.parent / "config.json"


def save_settings_to_file() -> None:
    """Save current settings to JSON file for persistence."""
    settings = {
        'gateway_url': st.session_state.gateway_url,
        'api_token': st.session_state.api_token,
        'theme': st.session_state.theme,
        'font_size': st.session_state.font_size,
        'debug_mode': st.session_state.debug_mode,
        'auto_refresh': st.session_state.auto_refresh
    }

    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        st.error(f"Failed to save settings to file: {str(e)}")


def load_settings_from_file() -> dict:
    """Load settings from JSON file.

    Returns:
        dict: Settings dictionary, or empty dict if file doesn't exist
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Failed to load settings from file: {str(e)}")
    return {}


def validate_gateway_url(url: str) -> tuple[bool, str]:
    """Validate gateway URL format.

    Args:
        url: Gateway URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "Gateway URL cannot be empty"

    if not url.startswith(('http://', 'https://')):
        return False, "Gateway URL must start with http:// or https://"

    # Basic URL validation
    try:
        from urllib.parse import urlparse
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "Invalid URL format"
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"

    return True, ""


def render() -> None:
    """Render the Settings page."""
    st.title("⚙️ Settings")
    st.caption("Configure your ZeroClaw instance")

    # Load saved settings on first visit
    if 'settings_loaded' not in st.session_state:
        saved_settings = load_settings_from_file()
        if saved_settings:
            update_settings(
                gateway_url=saved_settings.get('gateway_url'),
                api_token=saved_settings.get('api_token'),
                theme=saved_settings.get('theme'),
                font_size=saved_settings.get('font_size'),
                debug_mode=saved_settings.get('debug_mode'),
                auto_refresh=saved_settings.get('auto_refresh')
            )
        st.session_state.settings_loaded = True

    # Gateway Configuration Section
    st.subheader("Gateway Configuration")

    with st.form("gateway_settings"):
        gateway_url = st.text_input(
            "Gateway URL",
            value=st.session_state.get('gateway_url', 'http://localhost:3000'),
            placeholder="http://localhost:3000",
            help="URL of the ZeroClaw gateway service"
        )

        api_token = st.text_input(
            "API Token",
            type="password",
            value=st.session_state.get('api_token', ''),
            placeholder="Optional authentication token",
            help="Optional bearer token for authenticated requests"
        )

        col1, col2 = st.columns(2)
        with col1:
            save_btn = st.form_submit_button("💾 Save Changes", use_container_width=True)
        with col2:
            test_btn = st.form_submit_button("🔍 Test Connection", use_container_width=True)

        if save_btn:
            # Validate URL
            is_valid, error_msg = validate_gateway_url(gateway_url)
            if not is_valid:
                st.error(f"❌ {error_msg}")
            else:
                # Update session state
                update_settings(
                    gateway_url=gateway_url,
                    api_token=api_token if api_token else None
                )

                # Save to file
                save_settings_to_file()

                st.success("✅ Settings saved successfully!")

        if test_btn:
            # Validate URL first
            is_valid, error_msg = validate_gateway_url(gateway_url)
            if not is_valid:
                st.error(f"❌ {error_msg}")
            else:
                try:
                    # Test connection
                    client = ZeroClawAPIClient(
                        base_url=gateway_url,
                        api_token=api_token if api_token else None
                    )
                    health = client.get_health()

                    if health.get('status') == 'ok':
                        st.success(f"✅ Connected! Gateway is healthy")

                        # Show additional info if available
                        if 'version' in health:
                            st.info(f"Version: {health['version']}")
                        if 'uptime' in health:
                            uptime_hours = health['uptime'] / 3600
                            st.info(f"Uptime: {uptime_hours:.1f} hours")
                    else:
                        error = health.get('error', 'Unknown error')
                        st.error(f"❌ Connection failed: {error}")

                except Exception as e:
                    st.error(f"❌ Connection failed: {str(e)}")

    st.divider()

    # Appearance Section
    st.subheader("Appearance")

    col1, col2 = st.columns(2)

    with col1:
        # Theme selector
        theme_options = ["Matrix Green", "Dark", "Light"]
        current_theme = st.session_state.get('theme', 'matrix-green')

        # Map internal theme names to display names
        theme_map = {
            'matrix-green': 'Matrix Green',
            'dark': 'Dark',
            'light': 'Light'
        }
        reverse_theme_map = {v: k for k, v in theme_map.items()}

        current_theme_display = theme_map.get(current_theme, 'Matrix Green')
        current_index = theme_options.index(current_theme_display)

        selected_theme = st.selectbox(
            "Theme",
            theme_options,
            index=current_index,
            help="Only Matrix Green theme is currently available"
        )

        # Show disabled message for non-Matrix Green themes
        if selected_theme != "Matrix Green":
            st.caption("🚧 This theme is coming soon")
        else:
            # Update session state
            new_theme = reverse_theme_map[selected_theme]
            if st.session_state.get('theme') != new_theme:
                update_settings(theme=new_theme)
                save_settings_to_file()

    with col2:
        # Font size selector
        font_size_options = ["Small", "Medium", "Large"]
        current_font_size = st.session_state.get('font_size', 'medium')

        font_size_map = {
            'small': 'Small',
            'medium': 'Medium',
            'large': 'Large'
        }
        reverse_font_size_map = {v: k for k, v in font_size_map.items()}

        current_font_display = font_size_map.get(current_font_size, 'Medium')
        current_index = font_size_options.index(current_font_display)

        selected_font_size = st.selectbox(
            "Font Size",
            font_size_options,
            index=current_index,
            help="Adjust text size throughout the app"
        )

        # Update session state
        new_font_size = reverse_font_size_map[selected_font_size]
        if st.session_state.get('font_size') != new_font_size:
            update_settings(font_size=new_font_size)
            save_settings_to_file()

    st.divider()

    # Preferences Section
    st.subheader("Preferences")

    debug_mode = st.checkbox(
        "Enable Debug Mode",
        value=st.session_state.get('debug_mode', False),
        help="Show additional debugging information throughout the app"
    )

    if st.session_state.get('debug_mode') != debug_mode:
        update_settings(debug_mode=debug_mode)
        save_settings_to_file()

    auto_refresh = st.checkbox(
        "Auto-refresh Reports",
        value=st.session_state.get('auto_refresh', True),
        help="Automatically refresh report listings periodically"
    )

    if st.session_state.get('auto_refresh') != auto_refresh:
        update_settings(auto_refresh=auto_refresh)
        save_settings_to_file()

    # Debug Information Section (if debug mode enabled)
    if debug_mode:
        st.divider()
        st.subheader("Debug Information")

        debug_info = {
            "gateway_url": st.session_state.get('gateway_url'),
            "api_token_set": bool(st.session_state.get('api_token')),
            "theme": st.session_state.get('theme'),
            "font_size": st.session_state.get('font_size'),
            "auto_refresh": st.session_state.get('auto_refresh'),
            "config_file_exists": CONFIG_FILE.exists(),
            "config_file_path": str(CONFIG_FILE)
        }

        st.json(debug_info)

        # Additional session state info
        with st.expander("Full Session State"):
            # Filter out sensitive information
            filtered_state = {
                k: "***HIDDEN***" if k == 'api_token' else v
                for k, v in dict(st.session_state).items()
            }
            st.json(filtered_state)


# Entry point when page is loaded
if __name__ == "__main__":
    render()
