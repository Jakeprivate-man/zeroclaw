"""User Activity Chart Component.

ZeroClaw does not track individual user activity metrics. This component
displays an honest empty state directing users to the appropriate telemetry
source.
"""

import streamlit as st


def render() -> None:
    """Render honest empty state for user activity.

    ZeroClaw is a single-user agent runtime and does not collect user
    activity telemetry (active users, new users, returning users).
    This data would require gateway-level instrumentation.
    """
    st.info(
        "User activity metrics are not available. "
        "ZeroClaw is a single-user agent runtime and does not track "
        "individual user sessions. For multi-user metrics, integrate "
        "gateway telemetry: `zeroclaw gateway`"
    )
