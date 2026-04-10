from connectors.mcp.mcp_client import MCPClient


class LinearMCP:

    def __init__(self, server_url):
        self.client = MCPClient(server_url)

    def create_issue(self, title):

        return self.client.call_tool(
            "create_issue",
            {"title": title}
        )

    def list_issues(self):

        return self.client.call_tool(
            "list_issues",
            {}
        )