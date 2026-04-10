"""
backend/api/autonomous_router.py
API endpoints for Autonomous Agent features.
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json

from backend.agents.autonomous.autonomous_manager import AutonomousManager
from backend.llm.universal_provider import universal_provider

router = APIRouter(prefix="/api/v1/autonomous", tags=["autonomous"])

@router.post("/stream")
async def stream_autonomous(data: dict):
    manager = AutonomousManager(provider=universal_provider)

    async def event_generator():
        async for event in manager.stream(
            user_id=data.get("user_id"),
            bot_id=data.get("bot_id"),
            goal=data.get("goal")
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
