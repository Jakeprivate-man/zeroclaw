"""Budget management for ZeroClaw cost tracking.

This module provides budget calculation, enforcement checking, and
status reporting based on the config.toml settings and costs.jsonl data.
"""

import toml
import os
from pathlib import Path
from typing import Dict, Any, Optional, Literal
from enum import Enum
from lib.costs_parser import CostsParser


class BudgetStatus(str, Enum):
    """Budget status levels."""
    ALLOWED = "allowed"
    WARNING = "warning"
    EXCEEDED = "exceeded"
    DISABLED = "disabled"


class BudgetManager:
    """Manager for budget calculations and enforcement.

    Reads budget limits from config.toml and compares against
    actual costs from costs.jsonl to determine budget status.
    """

    def __init__(self, config_file: Optional[str] = None, costs_parser: Optional[CostsParser] = None):
        """Initialize the budget manager.

        Args:
            config_file: Path to config.toml. If None, uses ~/.zeroclaw/config.toml
            costs_parser: CostsParser instance. If None, creates a new one.
        """
        if config_file is None:
            config_file = os.path.expanduser("~/.zeroclaw/config.toml")

        self.config_file = Path(config_file)
        self.costs_parser = costs_parser or CostsParser()
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
            Default config dict with cost tracking disabled
        """
        return {
            "cost": {
                "enabled": False,
                "daily_limit_usd": 10.0,
                "monthly_limit_usd": 100.0,
                "warn_at_percent": 80,
                "allow_override": False
            }
        }

    def is_enabled(self) -> bool:
        """Check if cost tracking is enabled.

        Returns:
            True if cost tracking is enabled in config, False otherwise
        """
        return self.config.get("cost", {}).get("enabled", False)

    def get_limits(self) -> Dict[str, float]:
        """Get budget limits from config.

        Returns:
            Dictionary with daily_limit_usd and monthly_limit_usd
        """
        cost_config = self.config.get("cost", {})
        return {
            "daily_limit_usd": float(cost_config.get("daily_limit_usd", 10.0)),
            "monthly_limit_usd": float(cost_config.get("monthly_limit_usd", 100.0)),
            "warn_at_percent": float(cost_config.get("warn_at_percent", 80))
        }

    def check_budget(self, period: Literal["daily", "monthly"] = "daily") -> Dict[str, Any]:
        """Check budget status for a given period.

        Args:
            period: Either "daily" or "monthly"

        Returns:
            Dictionary with budget check result:
            {
                "status": BudgetStatus,
                "current_usd": float,
                "limit_usd": float,
                "percent_used": float,
                "message": str
            }
        """
        if not self.is_enabled():
            return {
                "status": BudgetStatus.DISABLED,
                "current_usd": 0.0,
                "limit_usd": 0.0,
                "percent_used": 0.0,
                "message": "Cost tracking is disabled in config.toml"
            }

        # Get cost summary
        summary = self.costs_parser.get_cost_summary()
        limits = self.get_limits()

        # Select period
        if period == "daily":
            current = summary["daily_cost_usd"]
            limit = limits["daily_limit_usd"]
        else:
            current = summary["monthly_cost_usd"]
            limit = limits["monthly_limit_usd"]

        # Calculate percentage
        percent_used = (current / limit * 100) if limit > 0 else 0.0
        warn_threshold = limits["warn_at_percent"]

        # Determine status
        if percent_used >= 100:
            status = BudgetStatus.EXCEEDED
            message = f"{period.capitalize()} budget exceeded: ${current:.2f} / ${limit:.2f}"
        elif percent_used >= warn_threshold:
            status = BudgetStatus.WARNING
            message = f"{period.capitalize()} budget warning: {percent_used:.0f}% used (${current:.2f} / ${limit:.2f})"
        else:
            status = BudgetStatus.ALLOWED
            message = f"{period.capitalize()} budget OK: {percent_used:.0f}% used (${current:.2f} / ${limit:.2f})"

        return {
            "status": status,
            "current_usd": round(current, 4),
            "limit_usd": round(limit, 2),
            "percent_used": round(percent_used, 1),
            "message": message
        }

    def get_budget_summary(self) -> Dict[str, Any]:
        """Get comprehensive budget summary for all periods.

        Returns:
            Dictionary with budget status for daily, monthly, and session:
            {
                "enabled": bool,
                "daily": { budget check result },
                "monthly": { budget check result },
                "session": {
                    "cost_usd": float,
                    "tokens": int,
                    "requests": int
                },
                "limits": { daily_limit_usd, monthly_limit_usd, warn_at_percent }
            }
        """
        if not self.is_enabled():
            return {
                "enabled": False,
                "daily": self.check_budget("daily"),
                "monthly": self.check_budget("monthly"),
                "session": {"cost_usd": 0.0, "tokens": 0, "requests": 0},
                "limits": self.get_limits()
            }

        # Get cost summary
        summary = self.costs_parser.get_cost_summary()

        return {
            "enabled": True,
            "daily": self.check_budget("daily"),
            "monthly": self.check_budget("monthly"),
            "session": {
                "cost_usd": summary["session_cost_usd"],
                "tokens": summary["total_tokens"],
                "requests": summary["request_count"]
            },
            "limits": self.get_limits()
        }

    def get_status_color(self, status: BudgetStatus) -> str:
        """Get color for budget status (Matrix theme colors).

        Args:
            status: Budget status

        Returns:
            Hex color string
        """
        color_map = {
            BudgetStatus.ALLOWED: "#5FAF87",      # Mint green
            BudgetStatus.WARNING: "#F1FA8C",      # Yellow
            BudgetStatus.EXCEEDED: "#FF5555",     # Red
            BudgetStatus.DISABLED: "#87D7AF"      # Sea green
        }
        return color_map.get(status, "#5FAF87")

    def format_budget_alert(self, period: Literal["daily", "monthly"] = "daily") -> Optional[str]:
        """Format a budget alert message for display.

        Args:
            period: Either "daily" or "monthly"

        Returns:
            Alert message string if warning or exceeded, None if allowed/disabled
        """
        check = self.check_budget(period)
        status = check["status"]

        if status == BudgetStatus.DISABLED:
            return None

        if status == BudgetStatus.EXCEEDED:
            return f"🚨 {check['message']}"

        if status == BudgetStatus.WARNING:
            return f"⚠️ {check['message']}"

        return None


# Module-level singleton instance
budget_manager = BudgetManager()
