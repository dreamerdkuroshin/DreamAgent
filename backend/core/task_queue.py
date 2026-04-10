"""
backend/core/task_queue.py  (v2 — delegates to DragonflyManager)

Provides task enqueueing — Dragonfly/Redis if connected, otherwise in-process asyncio.
The manager handles auto-reconnect; this module just grabs the current client.
"""
import os
import logging
import asyncio
from typing import Callable, Any

logger = logging.getLogger(__name__)


def _get_redis_conn():
    """Always returns the live client (or None) from the self-healing manager."""
    from backend.core.dragonfly_manager import dragonfly
    return dragonfly.get_client()

# ── Task State Machine (Fix 3) ──
_USER_FAILED_TASKS = {}
_ALL_TASKS = {}

def update_task_state(task_id: str, diff: dict):
    if task_id in _ALL_TASKS:
        _ALL_TASKS[task_id].update(diff)

def cache_last_failed_task(user_id: str, task: dict):
    _USER_FAILED_TASKS[user_id] = task

def get_last_failed_task(user_id: str):
    return _USER_FAILED_TASKS.get(user_id)

def init_task_state(task_id: str, query: str):
    task = {
        "task_id": task_id,
        "status": "running",
        "query": query,
        "result": None,
        "attempt": 1
    }
    _ALL_TASKS[task_id] = task
    return task

def get_task_state(task_id: str):
    return _ALL_TASKS.get(task_id)



# Legacy name kept for backward compat — code that does `from backend.core.task_queue import redis_conn`
# will get the property below instead of a stale None.
class _RedisConnProxy:
    """Transparent proxy so existing `redis_conn.get(...)` calls still work."""
    def __getattr__(self, name):
        client = _get_redis_conn()
        if client is None:
            raise AttributeError(f"Dragonfly not connected — cannot call .{name}()")
        return getattr(client, name)

    def __bool__(self):
        return _get_redis_conn() is not None


redis_conn = _RedisConnProxy()


def _task_done_callback(task: asyncio.Task) -> None:
    """Log any crashes in fire-and-forget background tasks."""
    try:
        exc = task.exception()
        if exc:
            logger.error("Background task crashed: %s", exc, exc_info=exc)
    except asyncio.CancelledError:
        logger.info("Background task was cancelled: %s", task.get_name())


def enqueue_task(func: Callable, *args, **kwargs) -> None:
    """
    Enqueue a task for background execution.
    Uses Redis/RQ when Dragonfly is connected, falls back to asyncio task.
    """
    client = _get_redis_conn()

    if client:
        try:
            from rq import Queue
            q = Queue(connection=client)
            q.enqueue(func, *args, **kwargs)
            return
        except Exception as exc:
            logger.warning("RQ enqueue failed (%s). Falling back to in-process.", exc)

    # Windows / no-Redis fallback: run as asyncio background task
    if asyncio.iscoroutinefunction(func):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        task = loop.create_task(func(*args, **kwargs))
        task.add_done_callback(_task_done_callback)
    else:
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            loop.run_in_executor(None, lambda: func(*args, **kwargs))
        except Exception:
            func(*args, **kwargs)
