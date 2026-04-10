"""
backend/core/pubsub.py
Pub/Sub helpers backed by Dragonfly/Redis.
Used for streaming SSE token events across worker boundaries.
Falls back to in-process asyncio.Queue per channel when Dragonfly unavailable.
"""
import json
import asyncio
import logging
from typing import Any

from backend.core.dragonfly_client import get_dragonfly

logger = logging.getLogger(__name__)

# Fallback: channel -> list of asyncio.Queue subscribers
_SUBSCRIBERS: dict = {}


def publish(channel: str, event: Any) -> None:
    """Publish an event dict to a channel."""
    payload = json.dumps(event)
    df = get_dragonfly()
    if df:
        try:
            df.publish(channel, payload)
            return
        except Exception as exc:
            logger.warning("[PubSub] publish error: %s", exc)
    # Fallback — broadcast to all in-process subscribers
    for q in _SUBSCRIBERS.get(channel, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def subscribe_iter(channel: str, timeout: float = 300.0):
    """
    Async generator that yields events published to `channel`.
    Automatically stops after `timeout` seconds of silence.
    Usage:
        async for event in subscribe_iter("stream:task_123"):
            ...
    """
    df = get_dragonfly()
    if df:
        # Use a blocking-in-thread approach via asyncio.to_thread
        import redis as _redis
        raw_client = _redis.from_url(
            df.connection_pool.connection_kwargs.get("path") or
            f"redis://{df.connection_pool.connection_kwargs.get('host','localhost')}:"
            f"{df.connection_pool.connection_kwargs.get('port',6379)}/0",
            decode_responses=True
        )
        ps = raw_client.pubsub()
        ps.subscribe(channel)
        deadline = asyncio.get_event_loop().time() + timeout
        try:
            while asyncio.get_event_loop().time() < deadline:
                msg = await asyncio.to_thread(ps.get_message, ignore_subscribe_messages=True, timeout=0.5)
                if msg and msg.get("type") == "message":
                    try:
                        yield json.loads(msg["data"])
                    except Exception:
                        yield msg["data"]
        finally:
            ps.unsubscribe(channel)
            ps.close()
            raw_client.close()
        return

    # Fallback — in-process queue
    q: asyncio.Queue = asyncio.Queue()
    _SUBSCRIBERS.setdefault(channel, []).append(q)
    deadline = asyncio.get_event_loop().time() + timeout
    try:
        while asyncio.get_event_loop().time() < deadline:
            try:
                event = await asyncio.wait_for(q.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue
    finally:
        subs = _SUBSCRIBERS.get(channel, [])
        if q in subs:
            subs.remove(q)
