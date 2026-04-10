"""
backend/mcp/mcp_router.py
API Endpoint logic for Frontend dashboards adding MCP dependencies.
"""
from fastapi import APIRouter
from backend.mcp.mcp_manager import mcp_manager

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])

@router.post("/connect/stdio")
async def connect_stdio(data: dict):
    return await mcp_manager.connect_stdio(
        data["user_id"],
        data["bot_id"],
        data["name"],
        data["command"]
    )

@router.post("/connect/sse")
async def connect_sse(data: dict):
    return await mcp_manager.connect_sse(
        data["user_id"],
        data["bot_id"],
        data["name"],
        data["url"]
    )

@router.get("/tools")
async def list_tools(user_id: str, bot_id: str):
    return await mcp_manager.list_tools(user_id, bot_id)

@router.post("/execute")
async def execute(data: dict):
    return await mcp_manager.execute_tool(
        data["user_id"],
        data["bot_id"],
        data["tool"],
        data.get("arguments", {})
    )
