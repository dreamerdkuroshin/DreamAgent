from typing import Dict, Any, Callable
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Central registry for all tools (Gmail, Slack, Stripe, GitHub, Notion, Figma)."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, name: str, func: Callable, description: str = "") -> None:
        """Register a new tool."""
        self._tools[name] = {
            "function": func,
            "description": description
        }
        logger.info(f"Registered tool: {name}")

    def get_tool(self, name: str) -> Dict[str, Any]:
        """Get a specific tool."""
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, str]:
        """List all available tools and their descriptions."""
        return {name: metadata["description"] for name, metadata in self._tools.items()}

# Global tool registry instance
registry = ToolRegistry()
