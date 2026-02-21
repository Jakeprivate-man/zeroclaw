"""ZeroClaw Gateway API Client.

This module provides a clean Python interface to the ZeroClaw gateway API.

Example usage:
    >>> from lib.api_client import api
    >>>
    >>> # Check health
    >>> health = api.get_health()
    >>> print(health['status'])
    >>>
    >>> # List reports
    >>> reports = api.get_reports()
    >>> for report in reports:
    ...     print(f"{report['name']}: {report['size']} bytes")
    >>>
    >>> # Get report content
    >>> content = api.get_report_content('atomic-report.md')
    >>> print(content[:100])
"""

import requests
from typing import Optional, Dict, List, Any
from datetime import datetime


class ZeroClawAPIClient:
    """Client for interacting with the ZeroClaw gateway API.

    This client provides methods for accessing reports, checking health,
    and retrieving metrics from the ZeroClaw gateway service.
    """

    def __init__(self, base_url: str = "http://localhost:3000", api_token: Optional[str] = None):
        """Initialize API client.

        Args:
            base_url: Gateway base URL (default: http://localhost:3000)
            api_token: Optional API token for authentication (not currently used)
        """
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.session = requests.Session()

        # Set default timeout for all requests
        self.session.request = lambda *args, **kwargs: requests.Session.request(
            self.session, *args, **{**kwargs, 'timeout': kwargs.get('timeout', 30)}
        )

        # Add authorization header if token provided
        if api_token:
            self.session.headers['Authorization'] = f'Bearer {api_token}'

        # Set common headers
        self.session.headers['User-Agent'] = 'ZeroClaw-Streamlit-Client/1.0'

    def get_health(self) -> Dict[str, Any]:
        """Check gateway health status.

        Makes a GET request to /health endpoint.

        Returns:
            dict with fields:
                - status (str): Health status (e.g., 'ok', 'error')
                - uptime (float, optional): Service uptime in seconds
                - version (str, optional): Service version
                - error (str, optional): Error message if status is not ok

        Raises:
            requests.exceptions.RequestException: If request fails
            requests.exceptions.Timeout: If request times out
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=10  # Shorter timeout for health checks
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {
                'status': 'error',
                'error': 'Health check timed out after 10 seconds'
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'error',
                'error': f'Could not connect to gateway at {self.base_url}'
            }
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'error': f'Health check failed: {str(e)}'
            }

    def get_reports(self) -> List[Dict[str, Any]]:
        """List all available reports.

        Makes a GET request to /api/reports endpoint.

        Returns:
            List of report metadata dicts, each containing:
                - name (str): Report filename
                - path (str): Full path to report
                - size (int): File size in bytes
                - modified (str): Last modified timestamp
                - created (str): Creation timestamp
                - type (str, optional): Report type
                - status (str, optional): Report status

        Raises:
            requests.exceptions.RequestException: If request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/reports",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise TimeoutError('Request timed out after 30 seconds')
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f'Could not connect to gateway at {self.base_url}')
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f'Failed to fetch reports: {str(e)}')

    def get_report_metadata(self, filename: str) -> Dict[str, Any]:
        """Get report metadata.

        Makes a GET request to /api/reports/{filename} endpoint.

        Args:
            filename: Report filename (e.g., 'atomic-report.md')

        Returns:
            Report metadata dict with fields:
                - filename (str): Report filename
                - content (str): Report content (markdown)
                - html (str, optional): HTML-rendered content
                - type (str): Report type

        Raises:
            requests.exceptions.RequestException: If request fails
            ValueError: If filename is empty
        """
        if not filename:
            raise ValueError('filename cannot be empty')

        try:
            response = self.session.get(
                f"{self.base_url}/api/reports/{filename}",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise FileNotFoundError(f'Report not found: {filename}')
            raise RuntimeError(f'Failed to fetch report metadata: {str(e)}')
        except requests.exceptions.Timeout:
            raise TimeoutError('Request timed out after 30 seconds')
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f'Could not connect to gateway at {self.base_url}')
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f'Failed to fetch report metadata: {str(e)}')

    def get_report_content(self, filename: str) -> str:
        """Get raw markdown content of a report.

        Makes a GET request to /reports/{filename} endpoint.

        Args:
            filename: Report filename (e.g., 'atomic-report.md')

        Returns:
            Raw markdown content as string

        Raises:
            requests.exceptions.RequestException: If request fails
            ValueError: If filename is empty
        """
        if not filename:
            raise ValueError('filename cannot be empty')

        try:
            response = self.session.get(
                f"{self.base_url}/reports/{filename}",
                timeout=30
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise FileNotFoundError(f'Report not found: {filename}')
            raise RuntimeError(f'Failed to fetch report content: {str(e)}')
        except requests.exceptions.Timeout:
            raise TimeoutError('Request timed out after 30 seconds')
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f'Could not connect to gateway at {self.base_url}')
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f'Failed to fetch report content: {str(e)}')

    def get_metrics(self) -> str:
        """Get Prometheus-style metrics.

        Makes a GET request to /metrics endpoint.

        Returns:
            Raw metrics text in Prometheus format

        Raises:
            requests.exceptions.RequestException: If request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/metrics",
                timeout=30
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.Timeout:
            raise TimeoutError('Request timed out after 30 seconds')
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f'Could not connect to gateway at {self.base_url}')
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f'Failed to fetch metrics: {str(e)}')

    def close(self):
        """Close the session and cleanup resources."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Module-level singleton instance
api = ZeroClawAPIClient()

# Backward compatibility alias for tests
APIClient = ZeroClawAPIClient
