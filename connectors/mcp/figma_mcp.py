from connectors.mcp.mcp_client import MCPClient


class FigmaMCP:

    def __init__(self, server_url):
        self.client = MCPClient(server_url)

    def create_frame(self, name):

        return self.client.call_tool(
            "create_frame",
            {"name": name}
        )

    def export_design(self, file_id):

        return self.client.call_tool(
            "export_design",
            {"file_id": file_id}
        )