"""
backend/mcp/clients/stdio_client.py
Local MCP Stdio Client (for Anthropic format)
"""
import asyncio
import json
from backend.mcp.base_client import BaseMCPClient

class StdioMCPClient(BaseMCPClient):
    def __init__(self, command: list[str]):
        self.command = command
        self.process = None
        self.tools_cache = []

    async def connect(self):
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

    async def _send(self, payload: dict):
        message = json.dumps(payload) + "\n"
        self.process.stdin.write(message.encode())
        await self.process.stdin.drain()

        response = await self.process.stdout.readline()
        return json.loads(response.decode())

    async def list_tools(self):
        if self.tools_cache:
            return self.tools_cache

        res = await self._send({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        })
        # Standard MCP actually wraps inside 'result' block usually
        self.tools_cache = res.get("result", {}).get("tools", []) if "result" in res else res.get("tools", [])
        return self.tools_cache

    async def call_tool(self, name: str, arguments: dict):
        return await self._send({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        })

    async def close(self):
        if self.process:
            self.process.kill()
