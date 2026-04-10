"""
Stripe MCP Tools for DreamAgent
Tools integrated with Stripe Model Context Protocol
"""

from core.tool_schema import Tool
from core.tool_registry import ToolRegistry
from connectors.mcp.stripe_mcp import StripeMCP
import os

# Initialize Stripe MCP — wrapped so a missing MCP server doesn't crash the backend
STRIPE_MCP_URL = os.getenv("STRIPE_MCP_URL", "http://localhost:9105")
try:
    stripe_mcp = StripeMCP(STRIPE_MCP_URL)
except Exception as _e:
    stripe_mcp = None  # type: ignore
    print(f"[WARN] StripeMCP not available at startup ({_e}). Stripe MCP tools will return errors until configured.")


# Create tool registry
stripe_registry = ToolRegistry()


def stripe_list_customers(limit: int = 10):
    """List Stripe customers"""
    if stripe_mcp is None:
        return {"error": "Stripe MCP not configured"}
    return stripe_mcp.client.call_tool("list_customers", {"limit": limit})


def stripe_create_customer(email: str, name: str = None):  # type: ignore[assignment]
    """Create a new Stripe customer"""
    if stripe_mcp is None:
        return {"error": "Stripe MCP not configured"}
    return stripe_mcp.client.call_tool(
        "create_customer",
        {"email": email, "name": name}
    )


def stripe_list_invoices(customer_id: str = None, limit: int = 10):  # type: ignore[assignment]
    """List Stripe invoices"""
    if stripe_mcp is None:
        return {"error": "Stripe MCP not configured"}
    return stripe_mcp.client.call_tool(
        "list_invoices",
        {"customer_id": customer_id, "limit": limit}
    )


def stripe_get_balance():
    """Get Stripe account balance"""
    if stripe_mcp is None:
        return {"error": "Stripe MCP not configured"}
    return stripe_mcp.client.call_tool("get_balance", {})


def stripe_list_charges(limit: int = 10):
    """List Stripe charges"""
    if stripe_mcp is None:
        return {"error": "Stripe MCP not configured"}
    return stripe_mcp.client.call_tool("list_charges", {"limit": limit})


def stripe_refund_charge(charge_id: str, amount: int = None):  # type: ignore[assignment]
    """Refund a Stripe charge"""
    if stripe_mcp is None:
        return {"error": "Stripe MCP not configured"}
    return stripe_mcp.client.call_tool(
        "refund_charge",
        {"charge_id": charge_id, "amount": amount}
    )



# Register all tools
stripe_registry.register(
    Tool(
        name="stripe_list_customers",
        description="List Stripe customers",
        function=stripe_list_customers
    )
)

stripe_registry.register(
    Tool(
        name="stripe_create_customer",
        description="Create a new Stripe customer",
        function=stripe_create_customer
    )
)

stripe_registry.register(
    Tool(
        name="stripe_list_invoices",
        description="List Stripe invoices",
        function=stripe_list_invoices
    )
)

stripe_registry.register(
    Tool(
        name="stripe_get_balance",
        description="Get Stripe account balance",
        function=stripe_get_balance
    )
)

stripe_registry.register(
    Tool(
        name="stripe_list_charges",
        description="List Stripe charges",
        function=stripe_list_charges
    )
)

stripe_registry.register(
    Tool(
        name="stripe_refund_charge",
        description="Refund a Stripe charge",
        function=stripe_refund_charge
    )
)
