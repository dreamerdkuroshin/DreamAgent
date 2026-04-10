"""
backend/mcp/registry.py
Global in-memory state repository for all connected MCP servers.
Strictly isolates tools natively by (user_id, bot_id).
"""
from typing import Dict, Tuple

class MCPRegistry:
    def __init__(self):
        # Maps (user_id, bot_id) -> { "server_name": BaseMCPClient }
        self._servers: Dict[Tuple[str, str], dict] = {}

    def get_bot_servers(self, user_id: str, bot_id: str):
        return self._servers.setdefault((user_id, bot_id), {})

    def add_server(self, user_id: str, bot_id: str, name: str, client):
        self.get_bot_servers(user_id, bot_id)[name] = client

    def get_server(self, user_id: str, bot_id: str, name: str):
        return self.get_bot_servers(user_id, bot_id).get(name)

    def remove_server(self, user_id: str, bot_id: str, name: str):
        self.get_bot_servers(user_id, bot_id).pop(name, None)

# Singleton global instance
mcp_registry = MCPRegistry()
