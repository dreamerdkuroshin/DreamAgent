"""
backend/mcp/mcp_manager.py
Core MCP Engine orchestrating bot-specific active client links.
"""
from backend.mcp.registry import mcp_registry
from backend.mcp.clients.stdio_client import StdioMCPClient
from backend.mcp.clients.sse_client import SSEClient

class MCPManager:
    async def ensure_bot_tools_connected(self, user_id: str, bot_id: str):
        """Cross-references SQLite InstalledTools against active RAM connections, auto-booting missing ones."""
        from backend.core.database import SessionLocal
        from backend.core.models import InstalledTool
        from backend.mcp.tool_registry import find_tool
        
        servers = mcp_registry.get_bot_servers(user_id, bot_id)
        db = SessionLocal()
        try:
            installed = db.query(InstalledTool).filter_by(user_id=user_id, bot_id=bot_id).all()
            for record in installed:
                if record.tool_id not in servers:
                    # Tool is installed in DB but connection is dead
                    tool = find_tool(record.tool_id)
                    if not tool:
                        continue
                        
                    print(f"[MCP] Auto-reconnecting dead tool '{tool['name']}' for bot {bot_id}...")
                    try:
                        if tool.get("connection") == "stdio":
                            await self.connect_stdio(user_id, bot_id, tool["id"], tool["command"])
                        elif tool.get("connection") == "sse":
                            await self.connect_sse(user_id, bot_id, tool["id"], tool["url"])
                    except Exception as e:
                        print(f"[MCP] Auto-reconnect failed for {tool['id']}: {e}")
        finally:
            db.close()

    async def connect_stdio(
        self,
        user_id: str,
        bot_id: str,
        name: str,
        command: list[str]
    ):
        client = StdioMCPClient(command)
        await client.connect()

        mcp_registry.add_server(user_id, bot_id, name, client)
        return {"status": "connected", "type": "stdio"}

    async def connect_sse(
        self,
        user_id: str,
        bot_id: str,
        name: str,
        url: str
    ):
        client = SSEClient(url)
        await client.connect()

        mcp_registry.add_server(user_id, bot_id, name, client)
        return {"status": "connected", "type": "sse"}

    async def list_tools(self, user_id: str, bot_id: str):
        await self.ensure_bot_tools_connected(user_id, bot_id)
        servers = mcp_registry.get_bot_servers(user_id, bot_id)
        all_tools = []

        for name, client in servers.items():
            try:
                tools = await client.list_tools()
                for t in tools:
                    t["server"] = name
                    t["source"] = "mcp" 
                    all_tools.append(t)
            except Exception as e:
                print(f"[MCP] Failed to list tools from {name}: {e}")

        return all_tools

    async def execute_tool(
        self,
        user_id: str,
        bot_id: str,
        tool_name: str,
        arguments: dict
    ):
        await self.ensure_bot_tools_connected(user_id, bot_id)
        servers = mcp_registry.get_bot_servers(user_id, bot_id)
        
        for name, client in servers.items():
            tools = await client.list_tools()
            for t in tools:
                if t["name"] == tool_name:
                    return await client.call_tool(tool_name, arguments)

        raise Exception(f"MCP Tool '{tool_name}' not found for bot {bot_id}")

    async def disconnect(
        self,
        user_id: str,
        bot_id: str,
        name: str
    ):
        client = mcp_registry.get_server(user_id, bot_id, name)
        if client:
            await client.close()
            mcp_registry.remove_server(user_id, bot_id, name)
        return {"status": "disconnected"}

# Singleton engine instance
mcp_manager = MCPManager()
