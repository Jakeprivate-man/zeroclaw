"""Agent Configuration Status component for displaying ZeroClaw agent info.

This component displays agent configuration and status:
- Current default agent
- Available configured agents
- Agent provider and model info
- Autonomy level
"""

import streamlit as st
from typing import Dict, Any
from lib.agent_monitor import agent_monitor


def render() -> None:
    """Render the agent configuration status component.

    Displays:
    - Default agent info
    - Configured agents list
    - Provider/model summary
    - Autonomy settings
    """
    st.subheader("🤖 Agent Configuration")

    try:
        status = agent_monitor.get_agent_status_summary()
    except Exception as e:
        st.error(f"Failed to load agent configuration: {str(e)}")
        return

    # Display agent count and autonomy level
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Total Agents",
            status["total_agents"],
            help="Number of configured agents (including default)"
        )

    with col2:
        autonomy = status["autonomy_level"]
        autonomy_icon = {
            "restricted": "🔒",
            "supervised": "👀",
            "autonomous": "🚀"
        }.get(autonomy, "⚙️")

        st.metric(
            "Autonomy Level",
            f"{autonomy_icon} {autonomy.title()}",
            help="Agent autonomy level from config"
        )

    with col3:
        provider_count = len(status["by_provider"])
        st.metric(
            "Providers",
            provider_count,
            help="Number of unique providers configured"
        )

    st.divider()

    # Default agent card
    st.markdown("**Default Agent**")
    default = status["default_agent"]
    _render_agent_card(default)

    # Configured agents (if any)
    configured = status["configured_agents"]
    if configured:
        st.divider()
        st.markdown("**Configured Agents**")

        for agent in configured:
            _render_agent_card(agent)
    else:
        st.info(
            "No additional agents configured. "
            "Add agents in `~/.zeroclaw/config.toml` under `[agents]` section."
        )

    # Provider summary
    if len(status["by_provider"]) > 1:
        st.divider()
        st.markdown("**Provider Distribution**")

        for provider, count in status["by_provider"].items():
            pct = (count / status["total_agents"]) * 100
            st.progress(pct / 100, text=f"{provider}: {count} agents ({pct:.0f}%)")


def _render_agent_card(agent: Dict[str, Any]) -> None:
    """Render a single agent configuration card.

    Args:
        agent: Agent configuration dict
    """
    with st.container():
        col1, col2 = st.columns([3, 1])

        with col1:
            # Agent name and model
            display_name = agent_monitor.format_agent_display_name(agent)
            st.markdown(f"**{display_name}**")

            # Provider and temperature
            provider = agent.get("provider", "unknown")
            temp = agent.get("temperature", 0.7)
            st.caption(f"Provider: {provider} • Temperature: {temp}")

        with col2:
            # Status badge
            status = agent.get("status", "unknown")
            status_color = {
                "configured": "#5FAF87",  # Green
                "running": "#87D7AF",     # Sea green
                "error": "#FF5555"        # Red
            }.get(status, "#87D7AF")

            st.markdown(
                f'<div style="text-align: right; color: {status_color}; '
                f'font-size: 0.8em; font-weight: bold;">{status.upper()}</div>',
                unsafe_allow_html=True
            )


# Expose main render function as the public API
__all__ = ['render']
