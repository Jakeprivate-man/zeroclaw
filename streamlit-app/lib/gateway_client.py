"""Enhanced Gateway Client - Team 4: Gateway Integration

Full gateway API integration with all endpoints.
Extends the basic API client with webhook management, pairing, and more.
"""

import requests
from typing import Optional, Dict, List, Any
from datetime import datetime
from dataclasses import dataclass
import logging

from lib.api_client import ZeroClawAPIClient

logger = logging.getLogger(__name__)


@dataclass
class WebhookInfo:
    """Information about a webhook."""
    id: str
    url: str
    events: List[str]
    secret: Optional[str]  # Masked
    enabled: bool
    created: datetime
    last_triggered: Optional[datetime]
    success_count: int
    failure_count: int


@dataclass
class PairingInfo:
    """Gateway pairing information."""
    require_pairing: bool
    is_paired: bool
    pairing_code: Optional[str]
    paired_devices: List[Dict[str, Any]]


class EnhancedGatewayClient(ZeroClawAPIClient):
    """Extended gateway client with full API support."""

    def __init__(self, base_url: str = "http://localhost:3000", api_token: Optional[str] = None):
        """Initialize enhanced gateway client.

        Args:
            base_url: Gateway base URL
            api_token: Optional API token
        """
        super().__init__(base_url, api_token)

    # Cost & Budget Endpoints

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost tracking summary.

        Returns:
            Dict with session, daily, monthly costs
        """
        try:
            response = self.session.get(f"{self.base_url}/api/cost-summary")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching cost summary: {e}")
            return {}

    def get_budget_status(self) -> Dict[str, Any]:
        """Get budget enforcement status.

        Returns:
            Dict with budget limits and current spend
        """
        try:
            response = self.session.get(f"{self.base_url}/api/budget-check")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching budget status: {e}")
            return {}

    # Agent Management Endpoints

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents.

        Returns:
            List of agent info dicts
        """
        try:
            response = self.session.get(f"{self.base_url}/api/agents")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing agents: {e}")
            return []

    def get_agent(self, name: str) -> Optional[Dict[str, Any]]:
        """Get specific agent information.

        Args:
            name: Agent name

        Returns:
            Agent info dict or None
        """
        try:
            response = self.session.get(f"{self.base_url}/api/agents/{name}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Error getting agent: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting agent: {e}")
            return None

    def start_agent(self, name: str) -> bool:
        """Start an agent.

        Args:
            name: Agent name

        Returns:
            True if started successfully
        """
        try:
            response = self.session.post(f"{self.base_url}/api/agents/{name}/start")
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error starting agent: {e}")
            return False

    def stop_agent(self, name: str) -> bool:
        """Stop an agent.

        Args:
            name: Agent name

        Returns:
            True if stopped successfully
        """
        try:
            response = self.session.post(f"{self.base_url}/api/agents/{name}/stop")
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error stopping agent: {e}")
            return False

    # Tool Execution Endpoints

    def get_tool_executions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get tool execution history.

        Args:
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of tool execution dicts
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/tool-executions",
                params={'limit': limit, 'offset': offset}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching tool executions: {e}")
            return []

    def get_pending_tools(self) -> List[Dict[str, Any]]:
        """Get pending tool approvals.

        Returns:
            List of pending tool call dicts
        """
        try:
            response = self.session.get(f"{self.base_url}/api/tool-calls/pending")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching pending tools: {e}")
            return []

    def approve_tool(self, tool_id: str) -> bool:
        """Approve a pending tool call.

        Args:
            tool_id: Tool call ID

        Returns:
            True if approved successfully
        """
        try:
            response = self.session.post(f"{self.base_url}/api/tool-calls/{tool_id}/approve")
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error approving tool: {e}")
            return False

    def reject_tool(self, tool_id: str, reason: str = "") -> bool:
        """Reject a pending tool call.

        Args:
            tool_id: Tool call ID
            reason: Rejection reason

        Returns:
            True if rejected successfully
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/tool-calls/{tool_id}/reject",
                json={'reason': reason}
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error rejecting tool: {e}")
            return False

    # Memory Operations

    def get_memory(self, category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get memory entries.

        Args:
            category: Optional category filter
            limit: Maximum results

        Returns:
            List of memory entry dicts
        """
        try:
            params = {'limit': limit}
            if category:
                params['category'] = category

            response = self.session.get(f"{self.base_url}/api/memory", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching memory: {e}")
            return []

    def store_memory(self, key: str, value: str, category: Optional[str] = None) -> bool:
        """Store a memory entry.

        Args:
            key: Memory key
            value: Memory value
            category: Optional category

        Returns:
            True if stored successfully
        """
        try:
            data = {'key': key, 'value': value}
            if category:
                data['category'] = category

            response = self.session.post(f"{self.base_url}/api/memory", json=data)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error storing memory: {e}")
            return False

    def search_memory(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search memory.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching memory entries
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/memory/search",
                json={'query': query, 'limit': limit}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching memory: {e}")
            return []

    def delete_memory(self, key: str) -> bool:
        """Delete a memory entry.

        Args:
            key: Memory key

        Returns:
            True if deleted successfully
        """
        try:
            response = self.session.delete(f"{self.base_url}/api/memory/{key}")
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error deleting memory: {e}")
            return False

    # Model & Provider Info

    def list_models(self) -> List[Dict[str, Any]]:
        """List available models.

        Returns:
            List of model info dicts
        """
        try:
            response = self.session.get(f"{self.base_url}/api/models")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing models: {e}")
            return []

    def list_providers(self) -> List[Dict[str, Any]]:
        """List available providers.

        Returns:
            List of provider info dicts
        """
        try:
            response = self.session.get(f"{self.base_url}/api/providers")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing providers: {e}")
            return []

    # Gateway Configuration

    def get_config(self) -> Dict[str, Any]:
        """Get gateway configuration.

        Returns:
            Configuration dict
        """
        try:
            response = self.session.get(f"{self.base_url}/api/config")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting config: {e}")
            return {}

    def update_config(self, config: Dict[str, Any]) -> bool:
        """Update gateway configuration.

        Args:
            config: New configuration

        Returns:
            True if updated successfully
        """
        try:
            response = self.session.post(f"{self.base_url}/api/config", json=config)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating config: {e}")
            return False

    # Pairing & Security

    def get_pairing_status(self) -> PairingInfo:
        """Get pairing status.

        Returns:
            PairingInfo object
        """
        try:
            response = self.session.get(f"{self.base_url}/api/gateway/pairing-status")
            response.raise_for_status()
            data = response.json()

            return PairingInfo(
                require_pairing=data.get('require_pairing', False),
                is_paired=data.get('is_paired', False),
                pairing_code=data.get('pairing_code'),
                paired_devices=data.get('paired_devices', [])
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting pairing status: {e}")
            return PairingInfo(
                require_pairing=False,
                is_paired=False,
                pairing_code=None,
                paired_devices=[]
            )

    # Webhook Management (if supported by gateway)

    def list_webhooks(self) -> List[WebhookInfo]:
        """List configured webhooks.

        Returns:
            List of WebhookInfo objects
        """
        # Note: This endpoint may not exist in current gateway
        try:
            response = self.session.get(f"{self.base_url}/api/webhooks")
            response.raise_for_status()
            data = response.json()

            webhooks = []
            for item in data:
                webhooks.append(WebhookInfo(
                    id=item['id'],
                    url=item['url'],
                    events=item.get('events', []),
                    secret='***' if item.get('secret') else None,
                    enabled=item.get('enabled', True),
                    created=datetime.fromisoformat(item['created']) if 'created' in item else datetime.now(),
                    last_triggered=datetime.fromisoformat(item['last_triggered']) if item.get('last_triggered') else None,
                    success_count=item.get('success_count', 0),
                    failure_count=item.get('failure_count', 0)
                ))

            return webhooks

        except requests.exceptions.RequestException as e:
            logger.warning(f"Webhook endpoint not available: {e}")
            return []


# Singleton instance
gateway_client = EnhancedGatewayClient()
