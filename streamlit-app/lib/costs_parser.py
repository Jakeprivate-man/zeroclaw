"""Cost tracking parser for ZeroClaw costs.jsonl file.

This module provides utilities to read and parse the costs.jsonl file
that ZeroClaw writes to ~/.zeroclaw/state/costs.jsonl.

Each line in the file is a JSON record representing a single API request:
{
    "id": "uuid",
    "session_id": "uuid",
    "model": "anthropic/claude-sonnet-4",
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801,
    "cost_usd": 0.0123,
    "timestamp": "2026-02-21T10:30:00Z"
}
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class CostsParser:
    """Parser for ZeroClaw cost tracking data.

    Reads the costs.jsonl file and provides aggregated cost summaries
    for session, daily, and monthly usage.
    """

    def __init__(self, costs_file: Optional[str] = None):
        """Initialize the costs parser.

        Args:
            costs_file: Path to costs.jsonl file. If None, uses default location
                       at ~/.zeroclaw/state/costs.jsonl
        """
        if costs_file is None:
            costs_file = os.path.expanduser("~/.zeroclaw/state/costs.jsonl")

        self.costs_file = Path(costs_file)

    def file_exists(self) -> bool:
        """Check if the costs file exists.

        Returns:
            True if file exists, False otherwise
        """
        return self.costs_file.exists()

    def read_all_records(self) -> List[Dict[str, Any]]:
        """Read all cost records from the file.

        Returns:
            List of cost record dictionaries
            Returns empty list if file doesn't exist or is invalid
        """
        if not self.file_exists():
            return []

        records = []
        try:
            with open(self.costs_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError:
                        # Skip invalid lines
                        continue
        except Exception:
            # If file can't be read, return empty list
            return []

        return records

    def get_cost_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated cost summary.

        Args:
            session_id: Optional session ID to filter by. If None, uses most recent session.

        Returns:
            Dictionary with cost summary:
            {
                "session_cost_usd": float,
                "daily_cost_usd": float,
                "monthly_cost_usd": float,
                "total_tokens": int,
                "request_count": int,
                "by_model": {
                    "model_name": {
                        "cost_usd": float,
                        "tokens": int,
                        "requests": int
                    }
                }
            }
        """
        records = self.read_all_records()

        if not records:
            return {
                "session_cost_usd": 0.0,
                "daily_cost_usd": 0.0,
                "monthly_cost_usd": 0.0,
                "total_tokens": 0,
                "request_count": 0,
                "by_model": {}
            }

        # Get current time boundaries
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # If no session_id specified, use the most recent one
        if session_id is None and records:
            session_id = records[-1].get('session_id')

        # Aggregate costs
        session_cost = 0.0
        daily_cost = 0.0
        monthly_cost = 0.0
        total_tokens = 0
        session_requests = 0
        by_model = defaultdict(lambda: {"cost_usd": 0.0, "tokens": 0, "requests": 0})

        for record in records:
            try:
                timestamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                cost = float(record.get('cost_usd', 0.0))
                tokens = int(record.get('total_tokens', 0))
                model = record.get('model', 'unknown')
                rec_session = record.get('session_id')

                # Session totals
                if rec_session == session_id:
                    session_cost += cost
                    total_tokens += tokens
                    session_requests += 1
                    by_model[model]["cost_usd"] += cost
                    by_model[model]["tokens"] += tokens
                    by_model[model]["requests"] += 1

                # Daily totals
                if timestamp >= today_start:
                    daily_cost += cost

                # Monthly totals
                if timestamp >= month_start:
                    monthly_cost += cost

            except (KeyError, ValueError, TypeError):
                # Skip invalid records
                continue

        return {
            "session_cost_usd": round(session_cost, 4),
            "daily_cost_usd": round(daily_cost, 4),
            "monthly_cost_usd": round(monthly_cost, 4),
            "total_tokens": total_tokens,
            "request_count": session_requests,
            "by_model": dict(by_model)
        }

    def get_recent_costs(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent cost records.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of records to return

        Returns:
            List of cost records within the time window, most recent first
        """
        records = self.read_all_records()

        if not records:
            return []

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = []

        for record in records:
            try:
                timestamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                if timestamp >= cutoff:
                    recent.append(record)
            except (KeyError, ValueError, TypeError):
                continue

        # Return most recent first, limited
        return list(reversed(recent[-limit:]))

    def get_token_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get token usage history for graphing.

        Args:
            hours: Number of hours to look back

        Returns:
            List of data points with timestamp and token counts:
            [
                {
                    "timestamp": "2026-02-21T10:30:00Z",
                    "input_tokens": 1234,
                    "output_tokens": 567,
                    "total_tokens": 1801,
                    "cost_usd": 0.0123
                }
            ]
        """
        records = self.get_recent_costs(hours=hours, limit=1000)

        return [
            {
                "timestamp": r.get('timestamp'),
                "input_tokens": r.get('input_tokens', 0),
                "output_tokens": r.get('output_tokens', 0),
                "total_tokens": r.get('total_tokens', 0),
                "cost_usd": r.get('cost_usd', 0.0)
            }
            for r in records
        ]


# Module-level singleton instance
costs_parser = CostsParser()


# Backward compatibility helper function for tests
def parse_costs(costs_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """Helper function to parse costs file and return all records.

    Args:
        costs_file: Path to costs.jsonl file. If None, uses default location.

    Returns:
        List of cost record dictionaries
    """
    parser = CostsParser(costs_file)
    return parser.read_all_records()
