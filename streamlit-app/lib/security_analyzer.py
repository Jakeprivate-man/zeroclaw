"""Security Analyzer - Team 3: Tool Approval System

Analyzes tool calls for security risks and provides risk assessments.
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class RiskCategory(Enum):
    """Categories of security risks."""
    DATA_EXFILTRATION = "data_exfiltration"
    SYSTEM_MODIFICATION = "system_modification"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    NETWORK_ACCESS = "network_access"
    FILE_MANIPULATION = "file_manipulation"
    CODE_EXECUTION = "code_execution"


@dataclass
class RiskAssessment:
    """Security risk assessment for a tool call."""
    risk_score: int  # 0-100
    risk_categories: List[RiskCategory]
    warnings: List[str]
    recommendations: List[str]
    allow_execution: bool


class SecurityAnalyzer:
    """Analyzes security risks of tool executions."""

    def __init__(self):
        """Initialize security analyzer."""
        self.sensitive_file_patterns = [
            r'/etc/passwd',
            r'/etc/shadow',
            r'\.ssh/.*',
            r'\.aws/.*',
            r'\.env',
            r'credentials',
            r'secrets?\..*',
        ]

        self.dangerous_command_patterns = [
            r'rm\s+-rf',
            r'sudo',
            r'chmod\s+777',
            r'chown',
            r'dd\s+if=',
            r'mkfs',
            r'fdisk',
            r'curl.*\|.*sh',
            r'wget.*\|.*sh',
        ]

        self.suspicious_domains = [
            'localhost',
            '127.0.0.1',
            '0.0.0.0',
            '::1',
            '192.168.',
            '10.',
            '172.16.',
        ]

    def analyze(self, tool_name: str, parameters: Dict[str, Any]) -> RiskAssessment:
        """Analyze a tool call for security risks.

        Args:
            tool_name: Name of tool
            parameters: Tool parameters

        Returns:
            RiskAssessment with risk score and recommendations
        """
        risk_score = 0
        risk_categories = []
        warnings = []
        recommendations = []

        # Analyze by tool type
        if tool_name == 'shell':
            risk_score, cats, warns, recs = self._analyze_shell(parameters)
            risk_categories.extend(cats)
            warnings.extend(warns)
            recommendations.extend(recs)

        elif tool_name in ['file_read', 'file_write', 'file_delete']:
            risk_score, cats, warns, recs = self._analyze_file_op(tool_name, parameters)
            risk_categories.extend(cats)
            warnings.extend(warns)
            recommendations.extend(recs)

        elif tool_name == 'http_request':
            risk_score, cats, warns, recs = self._analyze_http(parameters)
            risk_categories.extend(cats)
            warnings.extend(warns)
            recommendations.extend(recs)

        elif tool_name == 'browser':
            risk_score, cats, warns, recs = self._analyze_browser(parameters)
            risk_categories.extend(cats)
            warnings.extend(warns)
            recommendations.extend(recs)

        # Determine if execution should be allowed
        allow_execution = risk_score < 80  # Block if score >= 80

        return RiskAssessment(
            risk_score=risk_score,
            risk_categories=list(set(risk_categories)),  # Deduplicate
            warnings=warnings,
            recommendations=recommendations,
            allow_execution=allow_execution
        )

    def _analyze_shell(self, parameters: Dict[str, Any]) -> Tuple[int, List[RiskCategory], List[str], List[str]]:
        """Analyze shell command execution.

        Returns:
            Tuple of (risk_score, categories, warnings, recommendations)
        """
        command = parameters.get('command', '')
        risk_score = 50  # Base risk for shell
        categories = [RiskCategory.CODE_EXECUTION]
        warnings = []
        recommendations = []

        # Check for dangerous commands
        for pattern in self.dangerous_command_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                risk_score += 30
                warnings.append(f"Dangerous command pattern detected: {pattern}")
                categories.append(RiskCategory.SYSTEM_MODIFICATION)

        # Check for privilege escalation
        if re.search(r'\bsudo\b', command):
            risk_score += 20
            warnings.append("Privilege escalation detected (sudo)")
            categories.append(RiskCategory.PRIVILEGE_ESCALATION)

        # Check for piped execution
        if re.search(r'\|\s*(sh|bash|zsh)', command):
            risk_score += 20
            warnings.append("Piped execution detected")

        # Check for data exfiltration
        if re.search(r'curl|wget|nc|netcat', command):
            risk_score += 15
            warnings.append("Network tools detected - potential data exfiltration")
            categories.append(RiskCategory.DATA_EXFILTRATION)

        recommendations.append("Review command carefully before approving")
        if risk_score > 70:
            recommendations.append("Consider running in restricted environment")

        return risk_score, categories, warnings, recommendations

    def _analyze_file_op(self, tool_name: str, parameters: Dict[str, Any]) -> Tuple[int, List[RiskCategory], List[str], List[str]]:
        """Analyze file operations.

        Returns:
            Tuple of (risk_score, categories, warnings, recommendations)
        """
        path = parameters.get('path', '')
        risk_score = 20  # Base risk for file ops
        categories = [RiskCategory.FILE_MANIPULATION]
        warnings = []
        recommendations = []

        # Check for sensitive file patterns
        for pattern in self.sensitive_file_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                risk_score += 40
                warnings.append(f"Accessing sensitive file: {path}")
                categories.append(RiskCategory.DATA_EXFILTRATION)
                break

        # Check for system directories
        system_dirs = ['/etc/', '/sys/', '/proc/', '/dev/']
        if any(path.startswith(d) for d in system_dirs):
            risk_score += 30
            warnings.append("Accessing system directory")
            categories.append(RiskCategory.SYSTEM_MODIFICATION)

        # Higher risk for write/delete
        if tool_name in ['file_write', 'file_delete']:
            risk_score += 20
            recommendations.append("Verify file path is correct")

        recommendations.append("Ensure file path does not contain sensitive data")

        return risk_score, categories, warnings, recommendations

    def _analyze_http(self, parameters: Dict[str, Any]) -> Tuple[int, List[RiskCategory], List[str], List[str]]:
        """Analyze HTTP requests.

        Returns:
            Tuple of (risk_score, categories, warnings, recommendations)
        """
        url = parameters.get('url', '')
        method = parameters.get('method', 'GET')
        risk_score = 10  # Base risk for HTTP
        categories = [RiskCategory.NETWORK_ACCESS]
        warnings = []
        recommendations = []

        # Check for internal network access
        for domain in self.suspicious_domains:
            if domain in url:
                risk_score += 30
                warnings.append(f"Request to internal/local address: {url}")
                categories.append(RiskCategory.DATA_EXFILTRATION)
                break

        # Higher risk for POST/PUT/DELETE
        if method.upper() in ['POST', 'PUT', 'DELETE', 'PATCH']:
            risk_score += 15
            warnings.append(f"Write operation: {method}")

        # Check for credentials in URL
        if re.search(r'(password|token|key|secret)=', url, re.IGNORECASE):
            risk_score += 25
            warnings.append("Credentials detected in URL")

        recommendations.append("Verify URL is trusted")
        if risk_score > 40:
            recommendations.append("Review request headers and body")

        return risk_score, categories, warnings, recommendations

    def _analyze_browser(self, parameters: Dict[str, Any]) -> Tuple[int, List[RiskCategory], List[str], List[str]]:
        """Analyze browser automation.

        Returns:
            Tuple of (risk_score, categories, warnings, recommendations)
        """
        url = parameters.get('url', '')
        action = parameters.get('action', '')
        risk_score = 30  # Base risk for browser
        categories = [RiskCategory.CODE_EXECUTION, RiskCategory.NETWORK_ACCESS]
        warnings = []
        recommendations = []

        # Check URL
        for domain in self.suspicious_domains:
            if domain in url:
                risk_score += 20
                warnings.append(f"Browser navigating to internal address: {url}")

        # Check for click/type actions (potential interaction)
        if 'click' in action.lower() or 'type' in action.lower():
            risk_score += 15
            warnings.append("Browser interaction detected")

        recommendations.append("Verify browser action is safe")
        recommendations.append("Consider running in isolated environment")

        return risk_score, categories, warnings, recommendations

    def get_risk_color(self, risk_score: int) -> str:
        """Get color code for risk score (for UI).

        Args:
            risk_score: Risk score (0-100)

        Returns:
            Color string for UI display
        """
        if risk_score < 30:
            return "green"
        elif risk_score < 60:
            return "yellow"
        elif risk_score < 80:
            return "orange"
        else:
            return "red"

    def get_risk_label(self, risk_score: int) -> str:
        """Get risk label for score.

        Args:
            risk_score: Risk score (0-100)

        Returns:
            Risk label string
        """
        if risk_score < 30:
            return "Low Risk"
        elif risk_score < 60:
            return "Medium Risk"
        elif risk_score < 80:
            return "High Risk"
        else:
            return "Critical Risk"


# Singleton instance
security_analyzer = SecurityAnalyzer()
