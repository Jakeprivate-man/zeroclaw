"""Realtime Poller - Poll for new messages and trigger UI refresh.

This module provides real-time updates without WebSockets:
- Poll for new agent messages
- Update session state
- Trigger st.rerun() for UI refresh
- Configurable polling intervals
"""

import streamlit as st
import time
from typing import Optional, Dict, Any, List


class RealtimePoller:
    """Polls for new messages and updates UI in real-time.

    Uses Streamlit's st.rerun() instead of WebSockets for simplicity.

    Session state keys:
        - chat_polling: bool (whether polling is active)
        - chat_last_check: float (timestamp of last poll)
        - chat_poll_interval: int (seconds between polls)
        - chat_messages: List[Dict] (conversation messages)
    """

    def __init__(self):
        """Initialize the realtime poller."""
        # Initialize session state if needed
        if 'chat_polling' not in st.session_state:
            st.session_state.chat_polling = False

        if 'chat_last_check' not in st.session_state:
            st.session_state.chat_last_check = 0

        if 'chat_poll_interval' not in st.session_state:
            st.session_state.chat_poll_interval = 2  # Default: 2 seconds

        if 'chat_messages' not in st.session_state:
            st.session_state.chat_messages = []

        if 'chat_waiting_for_response' not in st.session_state:
            st.session_state.chat_waiting_for_response = False

    def start_polling(self) -> None:
        """Enable polling."""
        st.session_state.chat_polling = True
        st.session_state.chat_last_check = time.time()

    def stop_polling(self) -> None:
        """Disable polling."""
        st.session_state.chat_polling = False

    def is_polling(self) -> bool:
        """Check if polling is active.

        Returns:
            True if polling is enabled
        """
        return st.session_state.get('chat_polling', False)

    def should_poll_now(self) -> bool:
        """Check if it's time to poll again.

        Returns:
            True if poll interval has elapsed
        """
        if not self.is_polling():
            return False

        now = time.time()
        last_check = st.session_state.get('chat_last_check', 0)
        interval = st.session_state.get('chat_poll_interval', 2)

        return (now - last_check) >= interval

    def poll_for_updates(self) -> bool:
        """Poll for new messages from agent.

        This is a placeholder implementation. In production, this would:
        1. Check ZeroClaw agent API for new messages
        2. Compare with existing messages
        3. Append new messages to session state
        4. Return True if updates found

        Returns:
            True if new messages were found, False otherwise
        """
        if not self.should_poll_now():
            return False

        # Update last check time
        st.session_state.chat_last_check = time.time()

        # In a real implementation, you would:
        # 1. Call ZeroClaw agent API
        # 2. Get latest messages
        # 3. Compare with current messages
        # 4. Append new ones

        # For now, just a placeholder
        # If waiting for response, simulate getting one (mock behavior)
        if st.session_state.get('chat_waiting_for_response', False):
            # This would be replaced with actual API call
            # For demonstration purposes only
            return self._check_for_agent_response()

        return False

    def _check_for_agent_response(self) -> bool:
        """Check if agent has responded (placeholder).

        In production, this would check the ZeroClaw agent API.

        Returns:
            True if response found, False otherwise
        """
        # Placeholder: No actual checking yet
        # Real implementation would call agent API here
        return False

    def mark_waiting_for_response(self) -> None:
        """Mark that we're waiting for an agent response."""
        st.session_state.chat_waiting_for_response = True
        self.start_polling()

    def clear_waiting_for_response(self) -> None:
        """Clear the waiting flag."""
        st.session_state.chat_waiting_for_response = False
        self.stop_polling()

    def render_polling_indicator(self) -> None:
        """Render a visual indicator when polling is active."""
        if self.is_polling():
            with st.sidebar:
                st.markdown("""
                <div style="
                    background-color: rgba(95, 175, 135, 0.1);
                    border: 1px solid #5FAF87;
                    border-radius: 4px;
                    padding: 8px;
                    margin: 8px 0;
                    text-align: center;
                ">
                    <span style="color: #5FAF87;">
                        🔄 Polling for updates...
                    </span>
                </div>
                """, unsafe_allow_html=True)

    def get_poll_interval(self) -> int:
        """Get current polling interval.

        Returns:
            Polling interval in seconds
        """
        return st.session_state.get('chat_poll_interval', 2)

    def set_poll_interval(self, seconds: int) -> None:
        """Set polling interval.

        Args:
            seconds: Polling interval in seconds (1-60)
        """
        if 1 <= seconds <= 60:
            st.session_state.chat_poll_interval = seconds

    def render_poll_controls(self) -> None:
        """Render polling controls in sidebar."""
        with st.sidebar:
            st.markdown("### 🔄 Realtime Updates")

            # Polling toggle
            polling_enabled = st.checkbox(
                "Enable polling",
                value=self.is_polling(),
                key="polling_toggle"
            )

            if polling_enabled != self.is_polling():
                if polling_enabled:
                    self.start_polling()
                else:
                    self.stop_polling()

            # Interval slider (only if polling enabled)
            if self.is_polling():
                interval = st.slider(
                    "Poll interval (seconds):",
                    min_value=1,
                    max_value=60,
                    value=self.get_poll_interval(),
                    key="poll_interval_slider"
                )
                self.set_poll_interval(interval)

                # Show last check time
                last_check = st.session_state.get('chat_last_check', 0)
                if last_check:
                    elapsed = time.time() - last_check
                    st.caption(f"Last check: {elapsed:.1f}s ago")


def poll_and_update() -> bool:
    """Convenience function to poll and trigger rerun if updates found.

    Returns:
        True if updates were found
    """
    poller = RealtimePoller()

    if poller.poll_for_updates():
        st.rerun()
        return True

    return False


def auto_poll_in_background() -> None:
    """Auto-poll in background if enabled.

    Call this at the top of your page render function.
    """
    poller = RealtimePoller()

    # Only poll if polling is enabled
    if poller.should_poll_now():
        if poller.poll_for_updates():
            # New updates found, rerun UI
            st.rerun()


def start_waiting_for_response() -> None:
    """Start waiting for agent response and enable polling."""
    poller = RealtimePoller()
    poller.mark_waiting_for_response()


def stop_waiting_for_response() -> None:
    """Stop waiting for agent response and disable polling."""
    poller = RealtimePoller()
    poller.clear_waiting_for_response()
