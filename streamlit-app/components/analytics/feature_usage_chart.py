"""Feature Usage Chart Component.

ZeroClaw does not track per-feature usage counts. This component displays
an honest empty state.
"""

import streamlit as st


def render() -> None:
    """Render honest empty state for feature usage.

    ZeroClaw does not collect feature-level usage telemetry (tool usage
    counts, capability adoption, etc.). This data would require
    instrumentation in the tool execution layer.
    """
    st.info(
        "Feature usage metrics are not available. "
        "ZeroClaw does not currently track per-tool or per-capability "
        "usage counts. See the Delegations tab for agent-level analytics."
    )
