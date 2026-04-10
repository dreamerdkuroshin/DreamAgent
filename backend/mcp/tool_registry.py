"""
backend/mcp/tool_registry.py
Master dictionary of all available MCP plugins for the DreamAgent App Store.
"""
TOOLS = [
    {
        "id": "notion_query",
        "name": "Notion",
        "type": "mcp",
        "connection": "sse",
        "url": "http://localhost:3000",   # Dummy SSE server target
        "description": "Manage Notion pages natively"
    },
    {
        "id": "sqlite_query",
        "name": "SQLite",
        "type": "mcp",
        "connection": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-postgres", "postgres://user:pass@localhost/db"],
        "description": "Execute database queries explicitly"
    },
    {
        "id": "fetch",
        "name": "Web Fetch",
        "type": "mcp",
        "connection": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-fetch"],
        "description": "Scrape and synthesize raw websites"
    }
]

def find_tool(tool_id: str):
    for t in TOOLS:
        if t["id"] == tool_id:
            return t
    return None
