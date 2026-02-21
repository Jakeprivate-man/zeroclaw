"""Audit Logger - Team 3: Tool Approval System

Logs all tool approval decisions for security audit trail.
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """An audit log entry."""
    timestamp: datetime
    event_type: str  # approval, rejection, execution, error
    tool_name: str
    parameters: Dict[str, Any]
    approver: Optional[str]
    approved: bool
    reason: Optional[str] = None
    execution_result: Optional[str] = None


class AuditLogger:
    """Logs tool approval and execution events."""

    def __init__(self, log_file: str = "~/.zeroclaw/state/audit.jsonl"):
        """Initialize audit logger.

        Args:
            log_file: Path to audit log file
        """
        self.log_file = os.path.expanduser(log_file)

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def log_approval(self, tool_name: str, parameters: Dict[str, Any],
                     approver: str, approved: bool, reason: Optional[str] = None):
        """Log a tool approval/rejection event.

        Args:
            tool_name: Name of tool
            parameters: Tool parameters
            approver: Who approved/rejected
            approved: True if approved, False if rejected
            reason: Optional reason for rejection
        """
        entry = AuditEntry(
            timestamp=datetime.now(),
            event_type='approval' if approved else 'rejection',
            tool_name=tool_name,
            parameters=self._scrub_sensitive(parameters),
            approver=approver,
            approved=approved,
            reason=reason
        )

        self._write_entry(entry)

    def log_execution(self, tool_name: str, parameters: Dict[str, Any],
                      success: bool, result: Optional[str] = None):
        """Log a tool execution event.

        Args:
            tool_name: Name of tool
            parameters: Tool parameters
            success: True if execution succeeded
            result: Optional execution result
        """
        entry = AuditEntry(
            timestamp=datetime.now(),
            event_type='execution',
            tool_name=tool_name,
            parameters=self._scrub_sensitive(parameters),
            approver=None,
            approved=success,
            execution_result=result[:500] if result else None  # Truncate long results
        )

        self._write_entry(entry)

    def log_error(self, tool_name: str, parameters: Dict[str, Any],
                  error: str):
        """Log a tool error event.

        Args:
            tool_name: Name of tool
            parameters: Tool parameters
            error: Error message
        """
        entry = AuditEntry(
            timestamp=datetime.now(),
            event_type='error',
            tool_name=tool_name,
            parameters=self._scrub_sensitive(parameters),
            approver=None,
            approved=False,
            reason=error
        )

        self._write_entry(entry)

    def get_recent_entries(self, limit: int = 100) -> List[AuditEntry]:
        """Get recent audit entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of AuditEntry objects (most recent first)
        """
        if not os.path.exists(self.log_file):
            return []

        entries = []

        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            entry = self._parse_entry(data)
                            if entry:
                                entries.append(entry)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in audit log: {line[:50]}")
                            continue

        except Exception as e:
            logger.error(f"Error reading audit log: {e}")

        # Sort by timestamp (most recent first)
        entries.sort(key=lambda x: x.timestamp, reverse=True)

        return entries[:limit]

    def get_entries_by_tool(self, tool_name: str, limit: int = 50) -> List[AuditEntry]:
        """Get audit entries for a specific tool.

        Args:
            tool_name: Tool to filter by
            limit: Maximum entries to return

        Returns:
            List of matching AuditEntry objects
        """
        all_entries = self.get_recent_entries(limit=1000)  # Get more to filter
        filtered = [e for e in all_entries if e.tool_name == tool_name]
        return filtered[:limit]

    def get_entries_by_approver(self, approver: str, limit: int = 50) -> List[AuditEntry]:
        """Get audit entries by approver.

        Args:
            approver: Approver to filter by
            limit: Maximum entries to return

        Returns:
            List of matching AuditEntry objects
        """
        all_entries = self.get_recent_entries(limit=1000)
        filtered = [e for e in all_entries if e.approver == approver]
        return filtered[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit statistics.

        Returns:
            Dict with approval/rejection counts, etc.
        """
        entries = self.get_recent_entries(limit=1000)

        if not entries:
            return {
                'total_entries': 0,
                'approvals': 0,
                'rejections': 0,
                'executions': 0,
                'errors': 0
            }

        by_type = {}
        for entry in entries:
            event_type = entry.event_type
            if event_type not in by_type:
                by_type[event_type] = 0
            by_type[event_type] += 1

        # Count by approver
        by_approver = {}
        for entry in entries:
            if entry.approver:
                if entry.approver not in by_approver:
                    by_approver[entry.approver] = {'approvals': 0, 'rejections': 0}

                if entry.approved:
                    by_approver[entry.approver]['approvals'] += 1
                else:
                    by_approver[entry.approver]['rejections'] += 1

        return {
            'total_entries': len(entries),
            'approvals': by_type.get('approval', 0),
            'rejections': by_type.get('rejection', 0),
            'executions': by_type.get('execution', 0),
            'errors': by_type.get('error', 0),
            'by_approver': by_approver
        }

    def _write_entry(self, entry: AuditEntry):
        """Write an entry to the audit log.

        Args:
            entry: AuditEntry to write
        """
        try:
            with open(self.log_file, 'a') as f:
                data = asdict(entry)
                # Convert datetime to ISO format
                data['timestamp'] = entry.timestamp.isoformat()
                f.write(json.dumps(data) + '\n')

            logger.info(f"Logged audit event: {entry.event_type} - {entry.tool_name}")

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def _parse_entry(self, data: Dict[str, Any]) -> Optional[AuditEntry]:
        """Parse audit entry from JSON.

        Args:
            data: Raw entry data

        Returns:
            AuditEntry or None if parse fails
        """
        try:
            timestamp_str = data.get('timestamp')
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str)
            else:
                timestamp = datetime.now()

            return AuditEntry(
                timestamp=timestamp,
                event_type=data.get('event_type', 'unknown'),
                tool_name=data.get('tool_name', 'unknown'),
                parameters=data.get('parameters', {}),
                approver=data.get('approver'),
                approved=data.get('approved', False),
                reason=data.get('reason'),
                execution_result=data.get('execution_result')
            )

        except Exception as e:
            logger.error(f"Error parsing audit entry: {e}")
            return None

    def _scrub_sensitive(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from parameters.

        Args:
            parameters: Original parameters

        Returns:
            Scrubbed parameters dict
        """
        SENSITIVE_KEYS = {
            'api_key', 'api_token', 'password', 'secret',
            'bearer_token', 'authorization', 'credential'
        }

        scrubbed = parameters.copy()

        for key in scrubbed:
            if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
                scrubbed[key] = '***REDACTED***'

        return scrubbed


# Singleton instance
audit_logger = AuditLogger()
