"""
connectors/mcp/mcp_registry.py
MCP server registry with allowlist enforcement.

Only URLs that appear in the allowlist (loaded from MCP_ALLOWLIST_PATH or
set programmatically at startup) can be registered.  Runtime registration
of arbitrary URLs is rejected, preventing prompt-injection attacks from
redirecting a tool to an attacker-controlled server.

Allowlist file format (JSON):
    {
        "figma":   "https://mcp.figma.com",
        "linear":  "https://mcp.linear.app",
        "slack":   "https://mcp.slack.com"
    }
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


class MCPRegistry:
    """
    Registry of permitted MCP servers.

    Only servers whose URLs are pre-approved in the allowlist can be registered.
    Any attempt to register a URL not in the allowlist raises ValueError.
    """

    def __init__(self, allowlist_path: str = None):
        # Map of name → approved URL, loaded from config at startup.
        self._allowlist: dict[str, str] = {}
        # Map of name → currently active URL (subset of allowlist).
        self._servers: dict[str, str] = {}

        path = allowlist_path or os.getenv("MCP_ALLOWLIST_PATH")
        if path:
            self._load_allowlist(path)
        else:
            logger.warning(
                "MCPRegistry: MCP_ALLOWLIST_PATH not set. "
                "No servers will be allowed until the allowlist is configured."
            )

    # ------------------------------------------------------------------
    # Allowlist management (call at startup, not at runtime)
    # ------------------------------------------------------------------

    def _load_allowlist(self, path: str):
        try:
            with open(path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Allowlist must be a JSON object mapping name → URL.")
            self._allowlist = {k: v.rstrip("/") for k, v in data.items()}
            logger.info("MCPRegistry: loaded %d approved servers from %s.", len(self._allowlist), path)
        except Exception as e:
            logger.error("MCPRegistry: failed to load allowlist from '%s': %s", path, e)

    def add_to_allowlist(self, name: str, url: str):
        """
        Add a server to the allowlist programmatically.
        Call this only at application startup with trusted, hardcoded values.
        Never call this with values derived from user input.
        """
        self._allowlist[name] = url.rstrip("/")

    # ------------------------------------------------------------------
    # Runtime registration
    # ------------------------------------------------------------------

    def register(self, name: str, url: str):
        """
        Register a server by name.

        Raises ValueError if the URL is not in the pre-approved allowlist,
        preventing runtime injection of arbitrary server URLs.
        """
        approved_url = self._allowlist.get(name)
        if approved_url is None:
            raise ValueError(
                f"MCPRegistry: '{name}' is not in the server allowlist. "
                "Add it to the allowlist file before registering."
            )
        normalized = url.rstrip("/")
        if normalized != approved_url:
            raise ValueError(
                f"MCPRegistry: URL mismatch for '{name}'. "
                f"Expected '{approved_url}', got '{normalized}'."
            )
        self._servers[name] = normalized
        logger.info("MCPRegistry: registered server '%s' → %s", name, normalized)

    def get(self, name: str) -> str | None:
        return self._servers.get(name)

    def list_registered(self) -> list[str]:
        return list(self._servers.keys())

    def list_allowed(self) -> list[str]:
        return list(self._allowlist.keys())
