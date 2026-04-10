"""
backend/api/stream.py (Hardened)
Fix #4: Added max_polls timeout to prevent infinite connection leaks.
"""
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.core.state_manager import StateManager
from backend.core.task_queue import redis_conn

router = APIRouter(prefix="/api/v1/stream", tags=["stream"])
state_manager = StateManager(redis_conn)

MAX_POLL_SECONDS = 180  # User Request: SSE_TIMEOUT = 180


@router.get("/{task_id}")
async def stream_task_state(task_id: str):
    """
    Stream the execution state and logs for a given task using SSE.
    Fix #4: Closes after MAX_POLL_SECONDS regardless of task status.
    """
    async def event_generator():
        last_step = -1
        last_history_len = 0
        last_history_len = 0
        last_status = None
        elapsed = 0
        poll_interval = 1.0  # User Request: poll_interval = 1.0

        while elapsed < MAX_POLL_SECONDS:
            state = state_manager.load_state(task_id)

            if state.status == "pending" and not state.history:
                yield f"data: {json.dumps({'event': 'waiting', 'message': 'Waiting for task to start...'})}\n\n"
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue

            if state.current_step > last_step or len(state.history) > last_history_len or state.status != last_status:
                payload = {
                    "task_id": state.task_id,
                    "status": state.status,
                    "current_step": state.current_step,
                    "new_history": state.history[last_history_len:],
                    "result": state.result,
                }
                yield f"data: {json.dumps(payload)}\n\n"
                last_step = state.current_step
                last_history_len = len(state.history)
                last_status = state.status

            if state.status in ("completed", "failed", "cancelled"):
                yield f"data: {json.dumps({'event': 'done', 'status': state.status})}\n\n"
                return

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Timeout guard
        yield f"data: {json.dumps({'event': 'timeout', 'message': f'Stream closed after {MAX_POLL_SECONDS}s'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
