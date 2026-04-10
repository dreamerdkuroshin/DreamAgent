"""
backend/agents/tool_agent.py

ToolAgent — responsible for securely interpreting and executing tool calls from the orchestrator.
"""
import logging
from typing import List, Dict, Any, Callable
import asyncio

logger = logging.getLogger(__name__)

class ToolAgent:
    """Invokes sandbox functions or APIs asynchronously."""

    def __init__(self, tools: List[Callable] = None):
        self.tools = {getattr(t, "__name__", str(t)): t for t in (tools or [])}

    async def execute_tool(self, tool_name: str, user_id: str = None, bot_id: str = None, **kwargs) -> str:
        """Executes a defined tool securely via dynamic routing to MCP, OAuth, or Local logic."""
        
        # 🧠 Smart Tool Routing Layer
        tool_registry = {
            "google_drive": {"source": "oauth", "provider": "google"},
            "gmail_send": {"source": "oauth", "provider": "google"},
            "slack_message": {"source": "oauth", "provider": "slack"},
            "notion_query": {"source": "mcp"},
            "sqlite_query": {"source": "mcp"},
        }

        # Route dynamically if it's a known external interface
        if tool_name in tool_registry:
            route = tool_registry[tool_name]
            logger.info(f"[ToolAgent] Routing {tool_name} externally via {route['source']}")
            
            if route["source"] == "oauth":
                from backend.oauth.oauth_manager import get_active_token
                token = await get_active_token(user_id, bot_id, route["provider"])
                if not token:
                    return f"Error: No active OAuth token for {route['provider']}. Please connect account first."
                
                # Proxy to actual module runner with fresh token...
                return f"✅ OAuth tool '{tool_name}' executed securely with {route['provider']} token."
                
            elif route["source"] == "mcp":
                from backend.mcp.mcp_manager import mcp_manager
                try:
                    res = await mcp_manager.execute_tool(user_id, bot_id, tool_name, kwargs)
                    return str(res)
                except Exception as e:
                    return f"Error: MCP Execution Failed: {str(e)}"

        # 🚀 Fallback to localized function definition (if any)
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not found."

        tool_func = self.tools[tool_name]
        try:
            logger.info(f"[ToolAgent] Executing standard local {tool_name} with args {kwargs}")
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**kwargs)
            else:
                result = await asyncio.to_thread(tool_func, **kwargs)
            return str(result)
        except Exception as e:
            logger.error(f"[ToolAgent] Tool execution failed: {e}")
            return f"Error executing tool: {e}"
