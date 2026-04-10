from connectors.mcp.mcp_client import MCPClient


class StripeMCP:

    def __init__(self, server_url):

        self.client = MCPClient(server_url)

    def create_customer(self, email):

        return self.client.call_tool(
            "create_customer",
            {"email": email}
        )

    def create_payment(self, amount, currency):

        return self.client.call_tool(
            "create_payment",
            {
                "amount": amount,
                "currency": currency
            }
        )