"""Memory Reader - Team 2: Live Dashboard Data

Reads and monitors ZeroClaw memory store.
Provides real-time memory data for dashboard display.
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A memory entry from the store."""
    key: str
    value: str
    timestamp: datetime
    category: Optional[str] = None
    ttl: Optional[int] = None


class MemoryReader:
    """Reads ZeroClaw memory store data."""

    def __init__(self, memory_file: str = "~/.zeroclaw/memory_store.json"):
        """Initialize memory reader.

        Args:
            memory_file: Path to memory store file
        """
        self.memory_file = os.path.expanduser(memory_file)
        self.last_mtime: Optional[float] = None
        self.cached_data: Dict[str, Any] = {}

    def read_memory(self, force_reload: bool = False) -> Dict[str, Any]:
        """Read memory store.

        Args:
            force_reload: Force reload even if file hasn't changed

        Returns:
            Dict of memory entries
        """
        if not os.path.exists(self.memory_file):
            logger.warning(f"Memory file not found: {self.memory_file}")
            return {}

        try:
            # Check if file changed
            current_mtime = os.path.getmtime(self.memory_file)

            if not force_reload and self.last_mtime == current_mtime:
                return self.cached_data

            # Read file
            with open(self.memory_file, 'r') as f:
                data = json.load(f)

            self.cached_data = data
            self.last_mtime = current_mtime
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in memory file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error reading memory file: {e}")
            return {}

    def get_all_entries(self) -> List[MemoryEntry]:
        """Get all memory entries as structured data.

        Returns:
            List of MemoryEntry objects
        """
        data = self.read_memory()
        entries = []

        for key, value in data.items():
            # Handle both simple string values and complex objects
            if isinstance(value, str):
                entries.append(MemoryEntry(
                    key=key,
                    value=value,
                    timestamp=datetime.now()  # No timestamp in simple format
                ))
            elif isinstance(value, dict):
                entries.append(MemoryEntry(
                    key=key,
                    value=str(value.get('value', value)),
                    timestamp=datetime.fromisoformat(value['timestamp']) if 'timestamp' in value else datetime.now(),
                    category=value.get('category'),
                    ttl=value.get('ttl')
                ))

        return entries

    def search_memory(self, query: str) -> List[MemoryEntry]:
        """Search memory entries.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching MemoryEntry objects
        """
        all_entries = self.get_all_entries()
        query_lower = query.lower()

        matches = []
        for entry in all_entries:
            if query_lower in entry.key.lower() or query_lower in entry.value.lower():
                matches.append(entry)

        return matches

    def get_entry(self, key: str) -> Optional[MemoryEntry]:
        """Get a specific memory entry.

        Args:
            key: Memory key

        Returns:
            MemoryEntry or None if not found
        """
        data = self.read_memory()
        value = data.get(key)

        if value is None:
            return None

        if isinstance(value, str):
            return MemoryEntry(
                key=key,
                value=value,
                timestamp=datetime.now()
            )
        elif isinstance(value, dict):
            return MemoryEntry(
                key=key,
                value=str(value.get('value', value)),
                timestamp=datetime.fromisoformat(value['timestamp']) if 'timestamp' in value else datetime.now(),
                category=value.get('category'),
                ttl=value.get('ttl')
            )

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dict with entry count, file size, etc.
        """
        data = self.read_memory()

        if not os.path.exists(self.memory_file):
            return {
                'entry_count': 0,
                'file_size_kb': 0,
                'file_exists': False
            }

        file_size = os.path.getsize(self.memory_file)

        return {
            'entry_count': len(data),
            'file_size_kb': file_size / 1024,
            'file_exists': True,
            'last_modified': datetime.fromtimestamp(os.path.getmtime(self.memory_file))
        }

    def has_changed(self) -> bool:
        """Check if memory file has changed since last read.

        Returns:
            True if file was modified
        """
        if not os.path.exists(self.memory_file):
            return False

        try:
            current_mtime = os.path.getmtime(self.memory_file)
            return self.last_mtime is None or current_mtime > self.last_mtime
        except:
            return False

    def watch(self, callback: callable):
        """Watch memory file for changes and call callback.

        Args:
            callback: Function to call when file changes
        """
        if self.has_changed():
            self.read_memory(force_reload=True)
            callback()


class CostsReader:
    """Reads ZeroClaw cost tracking data."""

    def __init__(self, costs_file: str = "~/.zeroclaw/state/costs.jsonl"):
        """Initialize costs reader.

        Args:
            costs_file: Path to costs JSONL file
        """
        self.costs_file = os.path.expanduser(costs_file)

    def read_costs(self) -> List[Dict[str, Any]]:
        """Read all cost records.

        Returns:
            List of cost record dicts
        """
        if not os.path.exists(self.costs_file):
            return []

        records = []

        try:
            with open(self.costs_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            record = json.loads(line)
                            records.append(record)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON line in costs file: {line[:50]}")
                            continue

        except Exception as e:
            logger.error(f"Error reading costs file: {e}")

        return records

    def get_session_costs(self, session_id: str) -> List[Dict[str, Any]]:
        """Get costs for a specific session.

        Args:
            session_id: Session ID

        Returns:
            List of cost records for session
        """
        all_costs = self.read_costs()
        return [c for c in all_costs if c.get('session_id') == session_id]

    def get_daily_summary(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get cost summary for a day.

        Args:
            date: Date to summarize (default: today)

        Returns:
            Dict with total cost, token counts, etc.
        """
        if date is None:
            date = datetime.now()

        date_str = date.strftime('%Y-%m-%d')
        all_costs = self.read_costs()

        daily_costs = [
            c for c in all_costs
            if c.get('timestamp', '').startswith(date_str)
        ]

        total_cost = sum(c.get('cost_usd', 0) for c in daily_costs)
        total_tokens = sum(
            c.get('input_tokens', 0) + c.get('output_tokens', 0)
            for c in daily_costs
        )

        return {
            'date': date_str,
            'total_cost_usd': total_cost,
            'total_tokens': total_tokens,
            'request_count': len(daily_costs),
            'records': daily_costs
        }

    def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """Get cost summary for a month.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            Dict with total cost, breakdown by day, etc.
        """
        month_str = f"{year:04d}-{month:02d}"
        all_costs = self.read_costs()

        monthly_costs = [
            c for c in all_costs
            if c.get('timestamp', '').startswith(month_str)
        ]

        total_cost = sum(c.get('cost_usd', 0) for c in monthly_costs)
        total_tokens = sum(
            c.get('input_tokens', 0) + c.get('output_tokens', 0)
            for c in monthly_costs
        )

        # Group by model
        by_model = {}
        for c in monthly_costs:
            model = c.get('model', 'unknown')
            if model not in by_model:
                by_model[model] = {'cost': 0, 'tokens': 0, 'count': 0}

            by_model[model]['cost'] += c.get('cost_usd', 0)
            by_model[model]['tokens'] += c.get('input_tokens', 0) + c.get('output_tokens', 0)
            by_model[model]['count'] += 1

        return {
            'year': year,
            'month': month,
            'total_cost_usd': total_cost,
            'total_tokens': total_tokens,
            'request_count': len(monthly_costs),
            'by_model': by_model
        }


# Singleton instances
memory_reader = MemoryReader()
costs_reader = CostsReader()
