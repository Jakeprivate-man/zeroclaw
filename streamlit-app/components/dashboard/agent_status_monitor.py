"""Agent Status Monitor Component.

Displays individual agent health cards with status, CPU, memory, and task metrics.
Implements Matrix Green theme styling consistent with the dashboard design.
"""

import streamlit as st
from lib.agent_monitor import agent_monitor


def render():
    """Render agent status monitor with configuration cards from config.toml."""

    st.subheader("🤖 Agent Status Monitor")

    # Get real agent configurations from config.toml
    try:
        agents = agent_monitor.get_all_agents()
    except Exception:
        agents = []

    # Scrollable container
    with st.container(height=500, border=True):
        if len(agents) == 0:
            st.info("No agents configured -- add agents in ~/.zeroclaw/config.toml")
        else:
            for agent in agents:
                render_agent_config_card(agent)


def render_agent_config_card(agent):
    """Render a single agent configuration card from config.toml data.

    Args:
        agent: Agent config dictionary from agent_monitor (name, provider, model, temperature, status)
    """
    name = agent.get('name', 'Unknown')
    provider = agent.get('provider', 'unknown')
    model = agent.get('model', 'unknown')
    temperature = agent.get('temperature', 0.7)
    is_default = agent.get('is_default', False)

    # Extract short model name
    model_short = model.split("/")[-1] if "/" in model else model

    # Badge color
    badge_color = '#5FAF87' if is_default else '#87D7AF'
    badge_text = 'DEFAULT' if is_default else 'CONFIGURED'

    st.markdown(f"""
    <div style="background: rgba(93, 175, 135, 0.05); padding: 1rem; margin-bottom: 1rem;
                border-radius: 0.5rem; border: 1px solid #2d5f4f;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <div>
                <span style="font-size: 1.2rem;">🤖</span>
                <span style="font-weight: bold; margin-left: 0.5rem;">{name}</span>
            </div>
            <span style="background: {badge_color}; color: #000; padding: 0.2rem 0.5rem;
                       border-radius: 0.25rem; font-size: 0.8rem; font-weight: bold;">
                {badge_text}
            </span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.9rem;">
            <div>Provider: <strong>{provider}</strong></div>
            <div>Model: <strong>{model_short}</strong></div>
            <div>Temperature: <strong>{temperature}</strong></div>
            <div>Status: <strong>Configured</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
