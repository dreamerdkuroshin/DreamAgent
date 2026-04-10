"""
connectors/mcp/mcp_client.py
MCP (Model Context Protocol) client.

Security improvements over previous version:
  - access_token sent as Authorization: Bearer header (not in request body)
  - Server URL must use HTTPS (configurable for local dev via allow_http=True)
  - Explicit request timeouts to prevent hung connections
  - Session-level retry with backoff
"""

import logging
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10  # seconds


def _build_session(retries: int = 3) -> requests.Session:
    from urllib3.util.retry import Retry
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class MCPClient:
    """Client for interacting with an MCP-compatible tool server."""

    def __init__(
        self,
        server_url: str,
        access_token: str = None,
        allow_http: bool = False,
        timeout: int = _DEFAULT_TIMEOUT,
    ):
        parsed = urlparse(server_url)
        if not allow_http and parsed.scheme != "https":
            raise ValueError(
                f"MCPClient requires an HTTPS server URL. Got: '{server_url}'. "
                "Pass allow_http=True only for local development."
            )
        self.server_url = server_url.rstrip("/")
        self.access_token = access_token
        self.timeout = timeout
        self._session = _build_session()

    def _auth_headers(self) -> dict:
        """Return Authorization header dict; empty if no token configured."""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    def list_tools(self) -> list:
        """List all tools available on the MCP server."""
        r = self._session.get(
            f"{self.server_url}/tools",
            headers=self._auth_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        Call a tool on the MCP server.

        The access_token is sent as a Bearer header — it never appears in the
        request body and will not be captured by server-side access logs.
        """
        payload = {
            "tool": tool_name,
            "arguments": arguments,
            # access_token intentionally NOT included here
        }
        r = self._session.post(
            f"{self.server_url}/call",
            json=payload,
            headers=self._auth_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()
