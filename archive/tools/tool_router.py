from tools.calculator_tool import calculate
from tools.search_tool import search
from core.connector_manager import ConnectorManager
from core.tool_registry import ToolRegistry
from connectors.registry import ConnectorRegistry
import inspect

# NOTE: All connector imports are lazy (inside _execute_connector_tool) to avoid
# crashing the whole process if a connector's package path doesn't exist yet.

# Map connector names to their module + class paths for lazy resolution
_CONNECTOR_PATHS = {
    "gmail":       ("connectors.oauth.google.gmail", "GmailConnector"),
    "calendar":    ("connectors.oauth.google.calendar_connector", "GoogleCalendarConnector"),
    "drive":       ("connectors.oauth.google.drive", "GoogleDriveConnector"),
    "teams":       ("connectors.oauth.microsoft.teams", "TeamsConnector"),
    "excel":       ("connectors.oauth.microsoft.excel", "ExcelConnector"),
    "word":        ("connectors.oauth.microsoft.word", "WordConnector"),
    "powerpoint":  ("connectors.oauth.microsoft.powerpoint", "PowerPointConnector"),
    "slack":       ("connectors.oauth.slack", "SlackConnector"),
    "notion":      ("connectors.oauth.notion", "NotionConnector"),
    "stripe":      ("connectors.api_key.stripe", "StripeConnector"),
    "youtube":     ("connectors.oauth.google.youtube_connector", "YouTubeConnector"),
}


def _load_connector_class(tool_name: str):
    """Lazily import and return the connector class for tool_name, or None."""
    if tool_name not in _CONNECTOR_PATHS:
        return None
    module_path, class_name = _CONNECTOR_PATHS[tool_name]
    try:
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    except (ImportError, AttributeError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Could not load connector '%s' from '%s': %s", tool_name, module_path, exc
        )
        return None


class ToolRouter:
    """
    Advanced tool router supporting multiple tool sources:
    - Connector tools (Google, Microsoft, Slack, Notion, Stripe) via lazy imports
    - MCP-based tools with parametrization
    - Custom function tools (calculator, search)
    """

    def __init__(self):
        self.connector_registry = ConnectorRegistry()

        # Tool registries from MCP — loaded lazily to avoid startup failures
        self.tool_registries = {}
        for registry_name, module_path, attr in [
            ("slack",   "tools.slack_tools",   "slack_registry"),
            ("stripe",  "tools.stripe_tools",  "stripe_registry"),
        ]:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                self.tool_registries[registry_name] = getattr(mod, attr)
            except Exception:
                pass  # Registry unavailable — not fatal

    def run(self, tool_name, action=None, token=None, params=None, **kwargs):
        """
        Route tool requests to appropriate handlers.

        Supports three tool types:
        1. Connector tools: run(tool_name="gmail", action="list_messages", token=token)
        2. MCP tools: run(tool_name="send_slack_message", channel="#general", text="Hello")
        3. Legacy tools: run(tool_name="calculator", action="calculate", params={...})
        """
        params = {**(params or {}), **kwargs}

        # Check MCP registries first
        for registry in self.tool_registries.values():
            tool = registry.get(tool_name)
            if tool:
                return self._execute_mcp_tool(tool, params)

        # Connector tools
        if tool_name in _CONNECTOR_PATHS:
            return self._execute_connector_tool(tool_name, action, token, params)

        # Legacy built-in tools
        if tool_name == "calculator":
            return calculate(action or params.get("expression", ""))

        if tool_name == "search":
            return search(action or params.get("query", ""))

        return {"error": f"Tool '{tool_name}' not found"}

    def _execute_connector_tool(self, tool_name, action, token, params):
        """Execute a connector-based tool via lazy import."""
        connector_class = _load_connector_class(tool_name)
        if connector_class is None:
            return {"error": f"Connector '{tool_name}' is not available (import failed or missing)"}
        try:
            connector = connector_class(token=token)
            if not connector.is_available():
                return {"error": f"Connector '{tool_name}' is not configured/available."}
            return connector.execute(action, params)
        except Exception as exc:
            return {"error": f"Connector '{tool_name}' raised: {exc}"}

    def _execute_mcp_tool(self, tool, params):
        """Execute an MCP-based tool with dynamic parameters."""
        try:
            func = tool.function
            sig = inspect.signature(func)
            filtered_params = {k: v for k, v in params.items() if k in sig.parameters}
            return func(**filtered_params)
        except Exception as exc:
            return {"error": f"Failed to execute tool '{tool.name}'", "details": str(exc)}

    def list_tools(self, tool_type=None):
        """List available tools, optionally filtered by type."""
        tools = {
            "connectors": list(_CONNECTOR_PATHS.keys()),
            "mcp": {},
        }
        for registry_name, registry in self.tool_registries.items():
            tools["mcp"][registry_name] = [
                {"name": t.name, "description": t.description}
                for t in registry.list_tools()
            ]
        return tools

    def get_tool_schema(self, tool_name):
        """Get detailed schema for a specific tool."""
        for registry in self.tool_registries.values():
            tool = registry.get(tool_name)
            if tool:
                sig = inspect.signature(tool.function)
                return {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        param_name: {
                            "type": param.annotation.__name__
                            if hasattr(param.annotation, "__name__")
                            else str(param.annotation)
                        }
                        for param_name, param in sig.parameters.items()
                    },
                }
        return {"error": f"Tool '{tool_name}' not found"}


def run_tool(tool_name, input_data):
    """Legacy function for backward compatibility."""
    if tool_name == "calculator":
        return calculate(input_data)
    if tool_name == "search":
        return search(input_data)
    return "Tool not found"


# Global tool router instance
connector_manager = ConnectorManager()
default_router = ToolRouter()