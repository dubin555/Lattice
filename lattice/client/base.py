"""
Base client class providing common HTTP request functionality.
"""
from typing import Any, Dict, Optional

import requests

from lattice.exceptions import LatticeClientError


class BaseClient:
    """
    Base client class that provides common HTTP request methods.

    All client classes that need to communicate with the Lattice server
    should inherit from this class to ensure consistent error handling
    and request patterns.
    """

    def __init__(self, server_url: str = "http://localhost:8000"):
        """
        Initialize the base client.

        Args:
            server_url: The URL of the Lattice server.
        """
        self.server_url = server_url.rstrip("/")

    def _post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a POST request to the server.

        Args:
            endpoint: The API endpoint (e.g., "/create_workflow").
            data: Optional JSON data to send in the request body.

        Returns:
            The JSON response from the server.

        Raises:
            LatticeClientError: If the request fails or returns a non-200 status.
        """
        url = f"{self.server_url}{endpoint}"
        response = requests.post(url, json=data or {})

        if response.status_code != 200:
            raise LatticeClientError(
                f"Request to {endpoint} failed with status {response.status_code}",
                details={"response_text": response.text, "endpoint": endpoint}
            )

        return response.json()

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a GET request to the server.

        Args:
            endpoint: The API endpoint (e.g., "/status").
            params: Optional query parameters.

        Returns:
            The JSON response from the server.

        Raises:
            LatticeClientError: If the request fails or returns a non-200 status.
        """
        url = f"{self.server_url}{endpoint}"
        response = requests.get(url, params=params)

        if response.status_code != 200:
            raise LatticeClientError(
                f"Request to {endpoint} failed with status {response.status_code}",
                details={"response_text": response.text, "endpoint": endpoint}
            )

        return response.json()
