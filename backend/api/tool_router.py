"""
backend/api/tool_router.py
API mapping User Marketplace installs directly to the backend Model structures.
"""
from fastapi import APIRouter, HTTPException
from backend.core.database import SessionLocal
from backend.core.models import InstalledTool
from backend.mcp.tool_registry import find_tool, TOOLS
from backend.mcp.mcp_manager import mcp_manager
from backend.mcp.registry import mcp_registry

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

@router.get("/")
async def list_marketplace():
    return TOOLS


@router.get("/status")
async def tools_status(user_id: str, bot_id: str):
    """Returns each installed tool with live connection status from the MCP registry and OAuth manager."""
    db = SessionLocal()
    try:
        installed = db.query(InstalledTool).filter_by(user_id=user_id, bot_id=bot_id).all()
    finally:
        db.close()

    live_servers = mcp_registry.get_bot_servers(user_id, bot_id)

    result = []
    for record in installed:
        tool_meta = find_tool(record.tool_id) or {}
        is_connected = record.tool_id in live_servers
        result.append({
            "tool_id": record.tool_id,
            "name": tool_meta.get("name", record.tool_id),
            "type": tool_meta.get("type", "mcp"),
            "connection": tool_meta.get("connection", "stdio"),
            "description": tool_meta.get("description", ""),
            "connected": is_connected,
        })

    return {"tools": result}
    
@router.post("/install")
async def install_tool(data: dict):
    user_id = data.get("user_id")
    bot_id = data.get("bot_id")
    tool_id = data.get("tool_id")
    
    if not user_id or not bot_id or not tool_id:
        raise HTTPException(status_code=400, detail="Missing identifiers")

    tool = find_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found in Hub")

    # 1. Store in SQLite Marketplace bindings
    db = SessionLocal()
    try:
        exists = db.query(InstalledTool).filter_by(user_id=user_id, bot_id=bot_id, tool_id=tool_id).first()
        if not exists:
            record = InstalledTool(user_id=user_id, bot_id=bot_id, tool_id=tool_id)
            db.add(record)
            db.commit()
    finally:
        db.close()

    # 2. Automatically mount specific MCP runtime hooks based on metadata
    if tool.get("connection") == "stdio":
        return await mcp_manager.connect_stdio(
            user_id,
            bot_id,
            tool["id"],
            tool["command"]
        )

    elif tool.get("connection") == "sse":
        return await mcp_manager.connect_sse(
            user_id,
            bot_id,
            tool["id"],
            tool["url"]
        )

    return {"status": "installed", "message": f"Plugin {tool_id} added successfully!"}
