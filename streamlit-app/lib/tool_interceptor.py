"""Tool Interceptor - Team 3: Tool Approval System

Intercepts tool executions and provides approval workflow.
Security-critical component that prevents dangerous operations.
"""

import uuid
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolDangerLevel(Enum):
    """Danger level classification for tools."""
    SAFE = 0         # No approval needed (memory_recall, web_search)
    LOW = 1          # Approval recommended (http_request)
    MEDIUM = 2       # Approval required (file_read, file_write)
    HIGH = 3         # Always require approval (shell, browser)
    CRITICAL = 4     # Require admin approval (system commands)


@dataclass
class ToolCall:
    """A tool call waiting for approval."""
    id: str
    tool_name: str
    parameters: Dict[str, Any]
    danger_level: ToolDangerLevel
    timestamp: datetime
    approved: Optional[bool] = None
    approver: Optional[str] = None
    rejection_reason: Optional[str] = None
    executed: bool = False
    execution_result: Optional[Any] = None


class ToolInterceptor:
    """Intercepts and manages tool execution approvals."""

    def __init__(self):
        """Initialize tool interceptor."""
        self.pending_calls: Dict[str, ToolCall] = {}
        self.approved_calls: Dict[str, ToolCall] = {}
        self.rejected_calls: Dict[str, ToolCall] = {}
        self.danger_rules = self._init_danger_rules()

    def _init_danger_rules(self) -> Dict[str, ToolDangerLevel]:
        """Initialize danger level rules for tools.

        Returns:
            Dict mapping tool names to danger levels
        """
        return {
            # Safe tools
            'memory_recall': ToolDangerLevel.SAFE,
            'web_search': ToolDangerLevel.SAFE,
            'image_info': ToolDangerLevel.SAFE,

            # Low danger
            'http_request': ToolDangerLevel.LOW,

            # Medium danger
            'file_read': ToolDangerLevel.MEDIUM,
            'file_write': ToolDangerLevel.MEDIUM,
            'memory_store': ToolDangerLevel.MEDIUM,

            # High danger
            'shell': ToolDangerLevel.HIGH,
            'execute': ToolDangerLevel.HIGH,
            'browser': ToolDangerLevel.HIGH,
            'screenshot': ToolDangerLevel.HIGH,

            # Critical danger
            'system': ToolDangerLevel.CRITICAL,
            'sudo': ToolDangerLevel.CRITICAL,
            'delete_file': ToolDangerLevel.CRITICAL,
        }

    def intercept(self, tool_name: str, parameters: Dict[str, Any]) -> ToolCall:
        """Intercept a tool call for approval.

        Args:
            tool_name: Name of the tool being called
            parameters: Tool parameters

        Returns:
            ToolCall object (pending approval)
        """
        # Assess danger level
        danger_level = self._assess_danger(tool_name, parameters)

        # Create tool call record
        tool_call = ToolCall(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            parameters=parameters,
            danger_level=danger_level,
            timestamp=datetime.now()
        )

        # Add to pending queue
        self.pending_calls[tool_call.id] = tool_call

        logger.info(f"Intercepted tool call: {tool_name} ({danger_level.name})")

        return tool_call

    def approve(self, tool_call_id: str, approver: str = "user") -> bool:
        """Approve a pending tool call.

        Args:
            tool_call_id: ID of tool call to approve
            approver: Name/ID of approver

        Returns:
            True if approval successful
        """
        if tool_call_id not in self.pending_calls:
            logger.warning(f"Tool call not found: {tool_call_id}")
            return False

        tool_call = self.pending_calls[tool_call_id]
        tool_call.approved = True
        tool_call.approver = approver

        # Move to approved queue
        self.approved_calls[tool_call_id] = tool_call
        del self.pending_calls[tool_call_id]

        logger.info(f"Approved tool call: {tool_call.tool_name} by {approver}")

        return True

    def reject(self, tool_call_id: str, approver: str = "user", reason: str = "") -> bool:
        """Reject a pending tool call.

        Args:
            tool_call_id: ID of tool call to reject
            approver: Name/ID of approver
            reason: Reason for rejection

        Returns:
            True if rejection successful
        """
        if tool_call_id not in self.pending_calls:
            logger.warning(f"Tool call not found: {tool_call_id}")
            return False

        tool_call = self.pending_calls[tool_call_id]
        tool_call.approved = False
        tool_call.approver = approver
        tool_call.rejection_reason = reason

        # Move to rejected queue
        self.rejected_calls[tool_call_id] = tool_call
        del self.pending_calls[tool_call_id]

        logger.info(f"Rejected tool call: {tool_call.tool_name} by {approver}: {reason}")

        return True

    def get_pending(self) -> List[ToolCall]:
        """Get all pending tool calls.

        Returns:
            List of pending ToolCall objects
        """
        return list(self.pending_calls.values())

    def requires_approval(self, tool_call: ToolCall) -> bool:
        """Check if a tool call requires approval.

        Args:
            tool_call: ToolCall to check

        Returns:
            True if approval required
        """
        # Require approval for MEDIUM and above
        return tool_call.danger_level.value >= ToolDangerLevel.MEDIUM.value

    def auto_approve_safe(self) -> int:
        """Auto-approve all SAFE tools.

        Returns:
            Number of tools auto-approved
        """
        count = 0

        for tool_call_id, tool_call in list(self.pending_calls.items()):
            if tool_call.danger_level == ToolDangerLevel.SAFE:
                self.approve(tool_call_id, approver="auto")
                count += 1

        logger.info(f"Auto-approved {count} safe tools")
        return count

    def clear_pending(self) -> None:
        """Clear all pending approvals."""
        self.pending_calls.clear()

    def clear_approved(self) -> None:
        """Clear approved history."""
        self.approved_calls.clear()

    def clear_rejected(self) -> None:
        """Clear rejected history."""
        self.rejected_calls.clear()

    def _assess_danger(self, tool_name: str, parameters: Dict[str, Any]) -> ToolDangerLevel:
        """Assess danger level of a tool call.

        Args:
            tool_name: Name of tool
            parameters: Tool parameters

        Returns:
            ToolDangerLevel
        """
        # Check for dangerous patterns in parameters first (highest priority)
        pattern_danger = self._check_dangerous_patterns(tool_name, parameters)
        if pattern_danger:
            return pattern_danger

        # Check explicit rules
        if tool_name in self.danger_rules:
            return self.danger_rules[tool_name]

        # Default to MEDIUM for unknown tools
        return ToolDangerLevel.MEDIUM

    def _check_dangerous_patterns(self, tool_name: str, parameters: Dict[str, Any]) -> Optional[ToolDangerLevel]:
        """Check for dangerous patterns in tool parameters.

        Args:
            tool_name: Tool name
            parameters: Parameters to check

        Returns:
            ToolDangerLevel if dangerous patterns found, or None if no elevated risk
        """
        # Check for shell commands
        if tool_name == 'shell':
            command = parameters.get('command', '')

            # CRITICAL patterns - extremely dangerous
            critical_patterns = ['rm -rf', 'rm -fr', 'mkfs', 'dd if=', ':(){ :|:& };:']
            if any(pattern in command.lower() for pattern in critical_patterns):
                return ToolDangerLevel.CRITICAL

            # HIGH patterns - dangerous but not catastrophic
            high_patterns = ['sudo', 'chmod', 'chown']
            if any(pattern in command.lower() for pattern in high_patterns):
                return ToolDangerLevel.HIGH

        # Check for file operations on sensitive paths
        if tool_name in ['file_write', 'file_delete', 'file_read']:
            path = parameters.get('path', '')

            # CRITICAL paths - system-critical locations
            critical_paths = ['/etc/', '/sys/', '/proc/', '/boot/']
            if any(critical in path for critical in critical_paths):
                return ToolDangerLevel.CRITICAL

            # HIGH paths - sensitive user data
            high_paths = ['~/.ssh/', '~/.aws/', '~/.gnupg/']
            if any(sensitive in path for sensitive in high_paths):
                return ToolDangerLevel.HIGH

        # Check for network requests to sensitive domains
        if tool_name == 'http_request':
            url = parameters.get('url', '')
            sensitive_domains = ['localhost', '127.0.0.1', '0.0.0.0', '::1']
            if any(domain in url for domain in sensitive_domains):
                return ToolDangerLevel.MEDIUM

        return None


class ToolExecutor:
    """Executes approved tools with safety checks."""

    def __init__(self, interceptor: ToolInterceptor):
        """Initialize tool executor.

        Args:
            interceptor: ToolInterceptor to use for approvals
        """
        self.interceptor = interceptor
        self.tool_implementations: Dict[str, Callable] = {}

    def register_tool(self, name: str, implementation: Callable):
        """Register a tool implementation.

        Args:
            name: Tool name
            implementation: Function to execute tool
        """
        self.tool_implementations[name] = implementation

    def execute(self, tool_call_id: str) -> Any:
        """Execute an approved tool call.

        Args:
            tool_call_id: ID of approved tool call

        Returns:
            Tool execution result

        Raises:
            PermissionError: If tool not approved
            ValueError: If tool not found
        """
        # Check if approved
        if tool_call_id not in self.interceptor.approved_calls:
            raise PermissionError(f"Tool call not approved: {tool_call_id}")

        tool_call = self.interceptor.approved_calls[tool_call_id]

        # Check if implementation registered
        if tool_call.tool_name not in self.tool_implementations:
            raise ValueError(f"No implementation for tool: {tool_call.tool_name}")

        # Execute tool
        try:
            start_time = datetime.now()

            implementation = self.tool_implementations[tool_call.tool_name]
            result = implementation(**tool_call.parameters)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Record execution
            tool_call.executed = True
            tool_call.execution_result = result

            logger.info(f"Executed tool: {tool_call.tool_name} ({duration_ms:.0f}ms)")

            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_call.tool_name}: {e}")
            raise


# Singleton instance
tool_interceptor = ToolInterceptor()
