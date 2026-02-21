"""Session state initialization and management for Streamlit app.

This module provides centralized session state management, mirroring the
React Zustand stores used in the original application.
"""

import streamlit as st
from typing import Any, Dict, List, Optional
from datetime import datetime


def initialize_session_state() -> None:
    """Initialize all session state variables used across the app.

    Organizes state into logical groups matching the React Zustand stores:
    - Gateway state (gatewayStore)
    - Activity stream (activityStore)
    - Analytics (analyticsStore)
    - Reports (reportsStore)
    - Settings (settingsStore)
    - UI state (local component state)
    """

    defaults: Dict[str, Any] = {
        # Gateway state (gatewayStore)
        'gateway_health': None,
        'gateway_stats': None,
        'agents': [],
        'cpu_usage': 0,
        'memory_usage': 0,
        'metrics_history': {
            'active_agents': [],
            'requests_today': [],
            'reports_generated': [],
            'cpu_usage': []
        },
        'gateway_loading': False,
        'gateway_error': None,

        # Activity stream (activityStore)
        'activities': [],
        'activity_filter': 'all',
        'auto_scroll': True,
        'max_activities': 100,

        # Analytics (analyticsStore)
        'time_range': '7d',
        'analytics_data': None,
        'request_volume': [],
        'response_time': [],
        'error_rate': [],
        'user_activity': [],
        'analytics_loading': False,
        'analytics_error': None,

        # Reports (reportsStore)
        'reports': [],
        'selected_report': None,
        'report_content': None,
        'viewing_report': None,
        'reports_loading': False,
        'reports_error': None,

        # Settings (settingsStore)
        'gateway_url': 'http://localhost:3000',
        'api_token': '',
        'theme': 'matrix-green',
        'font_size': 'medium',
        'debug_mode': False,
        'auto_refresh': True,
        'refresh_interval': 5,  # seconds

        # UI state
        'last_update': None,
        'sidebar_expanded': True,
        'current_page': 'Dashboard',
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_session_state() -> None:
    """Clear all session state variables (useful for logout/reset).

    This function removes all keys from session state and reinitializes
    with default values. Useful for logout, reset, or switching contexts.
    """
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    initialize_session_state()


def update_gateway_state(
    health: Optional[Dict[str, Any]] = None,
    stats: Optional[Dict[str, Any]] = None,
    agents: Optional[List[Dict[str, Any]]] = None,
    error: Optional[str] = None
) -> None:
    """Update gateway-related session state.

    Args:
        health: Gateway health status data
        stats: Gateway statistics data
        agents: List of agent status objects
        error: Error message if request failed
    """
    if health is not None:
        st.session_state.gateway_health = health

    if stats is not None:
        st.session_state.gateway_stats = stats

        # Extract metrics for quick access
        if 'cpu_usage' in stats:
            st.session_state.cpu_usage = stats['cpu_usage']
        if 'memory_usage' in stats:
            st.session_state.memory_usage = stats['memory_usage']

    if agents is not None:
        st.session_state.agents = agents

    if error is not None:
        st.session_state.gateway_error = error

    st.session_state.last_update = datetime.now()


def add_activity(
    activity_type: str,
    message: str,
    icon: str = "ℹ️",
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Add a new activity to the activity stream.

    Args:
        activity_type: Type of activity (e.g., 'agent_started', 'error')
        message: Activity message text
        icon: Emoji icon for the activity
        metadata: Additional metadata about the activity
    """
    import random

    activity = {
        'id': f"activity-{random.randint(10000, 99999)}",
        'type': activity_type,
        'icon': icon,
        'message': message,
        'timestamp': int(datetime.now().timestamp()),
        'time_ago': 'Just now',
        'metadata': metadata or {}
    }

    # Add to beginning of list
    st.session_state.activities.insert(0, activity)

    # Trim to max activities
    max_activities = st.session_state.max_activities
    if len(st.session_state.activities) > max_activities:
        st.session_state.activities = st.session_state.activities[:max_activities]


def update_analytics_data(
    time_range: Optional[str] = None,
    request_volume: Optional[List[Dict[str, Any]]] = None,
    response_time: Optional[List[Dict[str, Any]]] = None,
    error_rate: Optional[List[Dict[str, Any]]] = None,
    error: Optional[str] = None
) -> None:
    """Update analytics-related session state.

    Args:
        time_range: Time range for analytics ('24h', '7d', '30d', '90d', '1y')
        request_volume: Request volume time series data
        response_time: Response time time series data
        error_rate: Error rate time series data
        error: Error message if analytics fetch failed
    """
    if time_range is not None:
        st.session_state.time_range = time_range

    if request_volume is not None:
        st.session_state.request_volume = request_volume

    if response_time is not None:
        st.session_state.response_time = response_time

    if error_rate is not None:
        st.session_state.error_rate = error_rate

    if error is not None:
        st.session_state.analytics_error = error


def update_reports_state(
    reports: Optional[List[Dict[str, Any]]] = None,
    selected_report: Optional[str] = None,
    report_content: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
) -> None:
    """Update reports-related session state.

    Args:
        reports: List of available reports
        selected_report: ID of currently selected report
        report_content: Content of the selected report
        error: Error message if report fetch failed
    """
    if reports is not None:
        st.session_state.reports = reports

    if selected_report is not None:
        st.session_state.selected_report = selected_report

    if report_content is not None:
        st.session_state.report_content = report_content

    if error is not None:
        st.session_state.reports_error = error


def update_settings(
    gateway_url: Optional[str] = None,
    api_token: Optional[str] = None,
    theme: Optional[str] = None,
    font_size: Optional[str] = None,
    debug_mode: Optional[bool] = None,
    auto_refresh: Optional[bool] = None,
    refresh_interval: Optional[int] = None
) -> None:
    """Update application settings in session state.

    Args:
        gateway_url: Gateway API URL
        api_token: API authentication token
        theme: UI theme ('matrix-green', 'dark', 'light')
        font_size: Font size setting ('small', 'medium', 'large')
        debug_mode: Whether debug mode is enabled
        auto_refresh: Whether auto-refresh is enabled
        refresh_interval: Auto-refresh interval in seconds
    """
    if gateway_url is not None:
        st.session_state.gateway_url = gateway_url

    if api_token is not None:
        st.session_state.api_token = api_token

    if theme is not None:
        st.session_state.theme = theme

    if font_size is not None:
        st.session_state.font_size = font_size

    if debug_mode is not None:
        st.session_state.debug_mode = debug_mode

    if auto_refresh is not None:
        st.session_state.auto_refresh = auto_refresh

    if refresh_interval is not None:
        st.session_state.refresh_interval = refresh_interval


def get_state(key: str, default: Any = None) -> Any:
    """Safely get a value from session state with a default.

    Args:
        key: Session state key
        default: Default value if key doesn't exist

    Returns:
        Value from session state or default
    """
    return st.session_state.get(key, default)


def set_state(key: str, value: Any) -> None:
    """Set a value in session state.

    Args:
        key: Session state key
        value: Value to set
    """
    st.session_state[key] = value


def has_state(key: str) -> bool:
    """Check if a key exists in session state.

    Args:
        key: Session state key to check

    Returns:
        True if key exists, False otherwise
    """
    return key in st.session_state


# Backward compatibility alias for tests
init_session_state = initialize_session_state
