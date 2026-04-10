from connectors.mcp.mcp_client import MCPClient


class MCPToolAdapter:

    def __init__(self, server_url):

        self.client = MCPClient(server_url)

    def list_tools(self):

        return self.client.list_tools()

    def run(self, tool_name, args):

        return self.client.call_tool(tool_name, args)