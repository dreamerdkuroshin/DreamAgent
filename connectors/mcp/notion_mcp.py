from connectors.mcp.mcp_client import MCPClient
from db.db import get_oauth_token


class NotionMCP:

    def __init__(self, server_url):
        token_data = get_oauth_token("notion")
        token = token_data.get("access_token") if token_data else None
        self.client = MCPClient(server_url, access_token=token)

    def create_page(self, title):

        return self.client.call_tool(
            "create_page",
            {"title": title}
        )

    def search(self, query):

        return self.client.call_tool(
            "search",
            {"query": query}
        )