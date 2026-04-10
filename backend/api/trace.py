"""
backend/api/trace.py

GET /api/trace/{task_id}   (frontend uses this)
GET /api/v1/trace/{task_id}  (API v1 path)

Returns the full step-trace for a task in JSON.
Used by the frontend AgentTracePanel for live observability.
"""
import json
import logging
from fastapi import APIRouter
from typing import Any, Dict, List

from backend.core.task_queue import redis_conn

router = APIRouter(prefix="/api/v1/trace", tags=["trace"])
# Alias router: the frontend AgentTracePanel fetches /api/trace/{taskId}
router_compat = APIRouter(prefix="/api/trace", tags=["trace"])
logger = logging.getLogger(__name__)


async def _get_trace_impl(task_id: str) -> Dict[str, Any]:
    """
    Return all recorded SSE events for a task as JSON.
    Works with both Dragonfly-backed and in-memory (Windows) task stores.
    """
    steps: List[Dict[str, Any]] = []
    status = "unknown"

    if redis_conn:
        # Dragonfly path
        raw_status = redis_conn.get(f"task:{task_id}:status")
        if raw_status:
            status = raw_status.decode("utf-8") if isinstance(raw_status, bytes) else raw_status

        events_raw = redis_conn.lrange(f"task:{task_id}:events", 0, -1)
        for raw in events_raw:
            try:
                event_data = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                steps.append(json.loads(event_data))
            except Exception:
                pass
    else:
        # In-memory fallback (Windows without Dragonfly)
        from backend.api.chat_worker import TASKS
        task_data = TASKS.get(task_id)
        if task_data:
            status = task_data.get("status", "unknown")
            steps = task_data.get("steps", [])

    return {
        "task_id": task_id,
        "status": status,
        "step_count": len(steps),
        "steps": steps,
    }


@router.get("/{task_id}")
async def get_trace(task_id: str) -> Dict[str, Any]:
    return await _get_trace_impl(task_id)


@router_compat.get("/{task_id}")
async def get_trace_compat(task_id: str) -> Dict[str, Any]:
    return await _get_trace_impl(task_id)

