"""
Slack MCP Tools for DreamAgent
Tools integrated with Slack Model Context Protocol
"""

from core.tool_schema import Tool
from core.tool_registry import ToolRegistry
from connectors.mcp.slack_mcp import SlackMCP
import os

# Initialize Slack MCP — wrapped so a missing MCP server doesn't crash the backend
SLACK_MCP_URL = os.getenv("SLACK_MCP_URL", "http://localhost:9104")
try:
    slack_mcp = SlackMCP(SLACK_MCP_URL)
except Exception as _e:
    slack_mcp = None  # type: ignore
    print(f"[WARN] SlackMCP not available at startup ({_e}). Slack tools will return errors until configured.")


# Create tool registry
slack_registry = ToolRegistry()


def send_slack_message(channel: str, text: str):
    """Send a message to a Slack channel"""
    if slack_mcp is None:
        return {"error": "Slack MCP not configured"}
    return slack_mcp.send_message(channel, text)


def slack_list_channels():
    """List all Slack channels"""
    if slack_mcp is None:
        return {"error": "Slack MCP not configured"}
    return slack_mcp.client.call_tool("list_channels", {})


def slack_list_users():
    """List all Slack users"""
    if slack_mcp is None:
        return {"error": "Slack MCP not configured"}
    return slack_mcp.client.call_tool("list_users", {})


def slack_get_user_info(user_id: str):
    """Get information about a specific Slack user"""
    if slack_mcp is None:
        return {"error": "Slack MCP not configured"}
    return slack_mcp.client.call_tool("get_user_info", {"user_id": user_id})


def slack_create_channel(channel_name: str, is_private: bool = False):
    """Create a new Slack channel"""
    if slack_mcp is None:
        return {"error": "Slack MCP not configured"}
    return slack_mcp.client.call_tool(
        "create_channel",
        {"channel_name": channel_name, "is_private": is_private}
    )


def slack_add_member_to_channel(channel: str, user_id: str):
    """Add a member to a Slack channel"""
    if slack_mcp is None:
        return {"error": "Slack MCP not configured"}
    return slack_mcp.client.call_tool(
        "add_member_to_channel",
        {"channel": channel, "user_id": user_id}
    )


def slack_upload_file(channel: str, file_path: str, file_name: str = None):  # type: ignore[assignment]
    """Upload a file to Slack"""
    if slack_mcp is None:
        return {"error": "Slack MCP not configured"}
    return slack_mcp.client.call_tool(
        "upload_file",
        {"channel": channel, "file_path": file_path, "file_name": file_name}
    )


def slack_set_user_status(status_text: str, emoji: str = None):  # type: ignore[assignment]
    """Set the user's status in Slack"""
    if slack_mcp is None:
        return {"error": "Slack MCP not configured"}
    return slack_mcp.client.call_tool(
        "set_status",
        {"status_text": status_text, "emoji": emoji}
    )



# Register all tools
slack_registry.register(
    Tool(
        name="send_slack_message",
        description="Send a message to a Slack channel",
        function=send_slack_message
    )
)

slack_registry.register(
    Tool(
        name="slack_list_channels",
        description="List all Slack channels",
        function=slack_list_channels
    )
)

slack_registry.register(
    Tool(
        name="slack_list_users",
        description="List all Slack users",
        function=slack_list_users
    )
)

slack_registry.register(
    Tool(
        name="slack_get_user_info",
        description="Get information about a specific Slack user",
        function=slack_get_user_info
    )
)

slack_registry.register(
    Tool(
        name="slack_create_channel",
        description="Create a new Slack channel",
        function=slack_create_channel
    )
)

slack_registry.register(
    Tool(
        name="slack_add_member_to_channel",
        description="Add a member to a Slack channel",
        function=slack_add_member_to_channel
    )
)

slack_registry.register(
    Tool(
        name="slack_upload_file",
        description="Upload a file to Slack",
        function=slack_upload_file
    )
)

slack_registry.register(
    Tool(
        name="slack_set_user_status",
        description="Set the user's status in Slack",
        function=slack_set_user_status
    )
)
