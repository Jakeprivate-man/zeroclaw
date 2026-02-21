"""Tool History Parser - Team 2: Live Dashboard Data

Parses tool execution logs and provides history for dashboard.
Works with tool approval system (Team 3) to track all tool executions.
"""

import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolDangerLevel(Enum):
    """Danger level for tools (shared with Team 3)."""
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ToolExecution:
    """Record of a tool execution."""
    id: str
    tool_name: str
    input_params: Dict[str, Any]
    output: Any
    success: bool
    duration_ms: float
    timestamp: datetime
    approved: bool
    approver: Optional[str]
    danger_level: ToolDangerLevel


class ToolHistoryParser:
    """Parses and manages tool execution history."""

    def __init__(self, history_file: str = "~/.zeroclaw/state/tool_history.jsonl"):
        """Initialize tool history parser.

        Args:
            history_file: Path to tool history log file
        """
        self.history_file = os.path.expanduser(history_file)

    def read_history(self, limit: Optional[int] = None) -> List[ToolExecution]:
        """Read tool execution history.

        Args:
            limit: Maximum number of records to return (most recent first)

        Returns:
            List of ToolExecution records
        """
        if not os.path.exists(self.history_file):
            return []

        records = []

        try:
            with open(self.history_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            execution = self._parse_execution(data)
                            if execution:
                                records.append(execution)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in tool history: {line[:50]}")
                            continue

        except Exception as e:
            logger.error(f"Error reading tool history: {e}")

        # Sort by timestamp (most recent first)
        records.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply limit
        if limit:
            records = records[:limit]

        return records

    def get_tool_stats(self) -> Dict[str, Any]:
        """Get statistics about tool usage.

        Returns:
            Dict with counts, success rates, etc.
        """
        history = self.read_history()

        if not history:
            return {
                'total_executions': 0,
                'success_rate': 0.0,
                'tools_by_name': {},
                'tools_by_danger': {}
            }

        # Count by tool name
        tools_by_name = {}
        for exec in history:
            name = exec.tool_name
            if name not in tools_by_name:
                tools_by_name[name] = {'count': 0, 'successes': 0, 'failures': 0}

            tools_by_name[name]['count'] += 1
            if exec.success:
                tools_by_name[name]['successes'] += 1
            else:
                tools_by_name[name]['failures'] += 1

        # Count by danger level
        tools_by_danger = {}
        for exec in history:
            level = exec.danger_level.name
            if level not in tools_by_danger:
                tools_by_danger[level] = 0
            tools_by_danger[level] += 1

        # Calculate success rate
        successes = sum(1 for e in history if e.success)
        success_rate = (successes / len(history) * 100) if history else 0

        return {
            'total_executions': len(history),
            'success_rate': success_rate,
            'tools_by_name': tools_by_name,
            'tools_by_danger': tools_by_danger
        }

    def get_recent_tools(self, count: int = 10) -> List[ToolExecution]:
        """Get most recent tool executions.

        Args:
            count: Number of recent executions to return

        Returns:
            List of recent ToolExecution records
        """
        return self.read_history(limit=count)

    def get_failed_tools(self, limit: Optional[int] = None) -> List[ToolExecution]:
        """Get failed tool executions.

        Args:
            limit: Maximum number to return

        Returns:
            List of failed ToolExecution records
        """
        all_history = self.read_history()
        failed = [e for e in all_history if not e.success]

        if limit:
            failed = failed[:limit]

        return failed

    def get_dangerous_tools(self, min_danger: ToolDangerLevel = ToolDangerLevel.MEDIUM) -> List[ToolExecution]:
        """Get executions of dangerous tools.

        Args:
            min_danger: Minimum danger level to include

        Returns:
            List of ToolExecution records for dangerous tools
        """
        all_history = self.read_history()
        return [e for e in all_history if e.danger_level.value >= min_danger.value]

    def append_execution(self, execution: ToolExecution) -> None:
        """Append a tool execution to history.

        Args:
            execution: ToolExecution to append
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)

        try:
            with open(self.history_file, 'a') as f:
                data = {
                    'id': execution.id,
                    'tool_name': execution.tool_name,
                    'input_params': execution.input_params,
                    'output': str(execution.output),
                    'success': execution.success,
                    'duration_ms': execution.duration_ms,
                    'timestamp': execution.timestamp.isoformat(),
                    'approved': execution.approved,
                    'approver': execution.approver,
                    'danger_level': execution.danger_level.name
                }
                f.write(json.dumps(data) + '\n')

        except Exception as e:
            logger.error(f"Error appending to tool history: {e}")

    def _parse_execution(self, data: Dict[str, Any]) -> Optional[ToolExecution]:
        """Parse execution data from JSON.

        Args:
            data: Raw execution data dict

        Returns:
            ToolExecution or None if parse fails
        """
        try:
            # Parse danger level
            danger_level_str = data.get('danger_level', 'SAFE')
            try:
                danger_level = ToolDangerLevel[danger_level_str]
            except KeyError:
                danger_level = ToolDangerLevel.SAFE

            # Parse timestamp
            timestamp_str = data.get('timestamp')
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str)
            else:
                timestamp = datetime.now()

            return ToolExecution(
                id=data.get('id', ''),
                tool_name=data.get('tool_name', 'unknown'),
                input_params=data.get('input_params', {}),
                output=data.get('output', ''),
                success=data.get('success', False),
                duration_ms=data.get('duration_ms', 0.0),
                timestamp=timestamp,
                approved=data.get('approved', False),
                approver=data.get('approver'),
                danger_level=danger_level
            )

        except Exception as e:
            logger.error(f"Error parsing tool execution: {e}")
            return None

    def clear_history(self) -> None:
        """Clear all tool history."""
        if os.path.exists(self.history_file):
            os.remove(self.history_file)


class LiveToolMonitor:
    """Monitors live tool executions for dashboard."""

    def __init__(self):
        """Initialize live tool monitor."""
        self.parser = ToolHistoryParser()
        self.last_count = 0

    def get_new_executions(self) -> List[ToolExecution]:
        """Get executions that appeared since last check.

        Returns:
            List of new ToolExecution records
        """
        all_executions = self.parser.read_history()
        current_count = len(all_executions)

        if current_count > self.last_count:
            new_count = current_count - self.last_count
            new_executions = all_executions[:new_count]
            self.last_count = current_count
            return new_executions

        return []

    def has_new_executions(self) -> bool:
        """Check if there are new executions.

        Returns:
            True if new executions are available
        """
        all_executions = self.parser.read_history()
        return len(all_executions) > self.last_count


# Singleton instances
tool_history_parser = ToolHistoryParser()
live_tool_monitor = LiveToolMonitor()
