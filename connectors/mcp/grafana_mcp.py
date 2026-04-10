from connectors.mcp.mcp_client import MCPClient


class GrafanaMCP:

    def __init__(self, server_url):

        self.client = MCPClient(server_url)

    def list_dashboards(self):

        return self.client.call_tool(
            "list_dashboards",
            {}
        )



    def query_metrics(self, query):

        return self.client.call_tool(
            "query_metrics",
            {"query": query}
        )