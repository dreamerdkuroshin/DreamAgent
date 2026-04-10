from connectors.mcp.mcp_client import MCPClient
from db.db import get_oauth_token


class SlackMCP:

    def __init__(self, server_url):
        token_data = get_oauth_token("slack")
        token = token_data.get("access_token") if token_data else None
        self.client = MCPClient(server_url, access_token=token)

    def send_message(self, channel, text):

        return self.client.call_tool(
            "send_message",
            {
                "channel": channel,
                "text": text
            }
        )