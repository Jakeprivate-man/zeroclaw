"""Agent status monitoring for ZeroClaw.

This module provides agent configuration parsing and status tracking
based on the config.toml file.
"""

import toml
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class AgentMonitor:
    """Monitor for agent configurations and status.

    Reads agent configurations from config.toml and provides
    information about available agents and their settings.
    """

    def __init__(self, config_file: Optional[str] = None):
        """Initialize the agent monitor.

        Args:
            config_file: Path to config.toml. If None, uses ~/.zeroclaw/config.toml
        """
        if config_file is None:
            config_file = os.path.expanduser("~/.zeroclaw/config.toml")

        self.config_file = Path(config_file)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from config.toml.

        Returns:
            Configuration dictionary
            Returns default values if file doesn't exist or is invalid
        """
        if not self.config_file.exists():
            return self._default_config()

        try:
            with open(self.config_file, 'r') as f:
                config = toml.load(f)
                return config
        except Exception:
            return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration.

        Returns:
            Default config dict
        """
        return {
            "default_provider": "openrouter",
            "default_model": "claude-sonnet-4-6",
            "default_temperature": 0.7,
            "agents": {}
        }

    def get_default_agent(self) -> Dict[str, Any]:
        """Get default agent configuration.

        Returns:
            Dictionary with default agent info:
            {
                "name": "default",
                "provider": str,
                "model": str,
                "temperature": float,
                "status": "configured",
                "is_default": True
            }
        """
        return {
            "name": "default",
            "provider": self.config.get("default_provider", "openrouter"),
            "model": self.config.get("default_model", "claude-sonnet-4-6"),
            "temperature": self.config.get("default_temperature", 0.7),
            "status": "configured",
            "is_default": True
        }

    def get_configured_agents(self) -> List[Dict[str, Any]]:
        """Get list of configured agents.

        Returns:
            List of agent configurations from [agents] section
            Each dict contains: name, provider, model, temperature, tools, etc.
        """
        agents_config = self.config.get("agents", {})

        if not agents_config:
            return []

        agents = []
        for name, config in agents_config.items():
            agent = {
                "name": name,
                "provider": config.get("provider", self.config.get("default_provider")),
                "model": config.get("model", self.config.get("default_model")),
                "temperature": config.get("temperature", self.config.get("default_temperature")),
                "status": "configured",
                "is_default": False
            }

            # Add optional fields if present
            if "tools" in config:
                agent["tools"] = config["tools"]
            if "max_iterations" in config:
                agent["max_iterations"] = config["max_iterations"]

            agents.append(agent)

        return agents

    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Get all available agents (default + configured).

        Returns:
            List of all agent configurations
        """
        agents = [self.get_default_agent()]
        agents.extend(self.get_configured_agents())
        return agents

    def get_agent_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get specific agent configuration by name.

        Args:
            name: Agent name

        Returns:
            Agent configuration dict, or None if not found
        """
        all_agents = self.get_all_agents()
        for agent in all_agents:
            if agent["name"] == name:
                return agent
        return None

    def get_agent_count(self) -> int:
        """Get total number of configured agents.

        Returns:
            Number of agents (including default)
        """
        return len(self.get_all_agents())

    def get_provider_summary(self) -> Dict[str, int]:
        """Get count of agents by provider.

        Returns:
            Dictionary mapping provider name to agent count
            Example: {"openrouter": 2, "anthropic": 1}
        """
        agents = self.get_all_agents()
        summary = {}

        for agent in agents:
            provider = agent.get("provider", "unknown")
            summary[provider] = summary.get(provider, 0) + 1

        return summary

    def get_model_summary(self) -> Dict[str, int]:
        """Get count of agents by model.

        Returns:
            Dictionary mapping model name to agent count
        """
        agents = self.get_all_agents()
        summary = {}

        for agent in agents:
            model = agent.get("model", "unknown")
            summary[model] = summary.get(model, 0) + 1

        return summary

    def get_agent_status_summary(self) -> Dict[str, Any]:
        """Get comprehensive agent status summary.

        Returns:
            Dictionary with:
            {
                "total_agents": int,
                "default_agent": dict,
                "configured_agents": list,
                "by_provider": dict,
                "by_model": dict,
                "autonomy_level": str,
                "tools_enabled": bool
            }
        """
        return {
            "total_agents": self.get_agent_count(),
            "default_agent": self.get_default_agent(),
            "configured_agents": self.get_configured_agents(),
            "by_provider": self.get_provider_summary(),
            "by_model": self.get_model_summary(),
            "autonomy_level": self.config.get("autonomy", {}).get("level", "supervised"),
            "tools_enabled": True  # Tools are always available
        }

    def format_agent_display_name(self, agent: Dict[str, Any]) -> str:
        """Format a display name for an agent.

        Args:
            agent: Agent configuration dict

        Returns:
            Formatted display name like "default (claude-sonnet-4)" or "researcher (gpt-4)"
        """
        name = agent.get("name", "unknown")
        model = agent.get("model", "unknown")

        # Extract short model name (last part after /)
        model_short = model.split("/")[-1] if "/" in model else model

        if agent.get("is_default"):
            return f"{name} ({model_short}) ⭐"
        return f"{name} ({model_short})"


# Module-level singleton instance
agent_monitor = AgentMonitor()
