"""
backend/mcp/clients/sse_client.py
Remote MCP HTTP Event Stream Client
"""
import httpx
from backend.mcp.base_client import BaseMCPClient

class SSEClient(BaseMCPClient):
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
        self.tools_cache = []

    async def connect(self):
        return True

    async def list_tools(self):
        if self.tools_cache:
            return self.tools_cache

        res = await self.client.get(f"{self.base_url}/tools")
        self.tools_cache = res.json()
        return self.tools_cache

    async def call_tool(self, name: str, arguments: dict):
        res = await self.client.post(
            f"{self.base_url}/tools/{name}",
            json=arguments
        )
        return res.json()

    async def close(self):
        await self.client.aclose()
