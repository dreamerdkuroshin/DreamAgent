"""
backend/core/queue.py  (v2 — backed by DragonflyManager)

Unified queue layer.
  ∙ Full mode  → Dragonfly/Redis lists  (lpush / brpop)
  ∙ Fallback   → DragonflyManager.local_queue list  (in-process FIFO)
  ∙ Local jobs are migrated to Dragonfly when connection is restored.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from backend.core.dragonfly_manager import dragonfly

logger = logging.getLogger(__name__)

BUILDER_QUEUE = "builder_queue"


def enqueue(queue_name: str, job: Any) -> None:
    """Push a serialized job onto the queue."""
    payload = json.dumps(job)
    client = dragonfly.get_client()

    if client:
        try:
            client.lpush(queue_name, payload)
            logger.info("[Queue] Pushed to '%s' (dragonfly): %s", queue_name, str(job)[:80])
            return
        except Exception as exc:
            logger.warning("[Queue] Dragonfly lpush error (%s), using local queue: %s", queue_name, exc)

    # Local fallback
    dragonfly.local_queue.append((queue_name, payload))
    logger.info("[Queue] Pushed to local_queue (fallback): %s", str(job)[:80])


def dequeue_blocking(queue_name: str, timeout: int = 5) -> Optional[Any]:
    """
    Pop one job from the queue.
    Returns deserialized job or None.
    """
    client = dragonfly.get_client()

    if client:
        try:
            result = client.brpop(queue_name, timeout=timeout)
            if result:
                _, raw = result
                return json.loads(raw)
        except Exception as exc:
            logger.warning("[Queue] Dragonfly brpop error: %s", exc)

    # Local fallback — scan list for matching queue_name
    for i, (qname, payload) in enumerate(dragonfly.local_queue):
        if qname == queue_name:
            dragonfly.local_queue.pop(i)
            return json.loads(payload)
    return None


def queue_length(queue_name: str) -> int:
    """Return number of waiting jobs."""
    client = dragonfly.get_client()
    if client:
        try:
            return client.llen(queue_name)
        except Exception:
            pass
    return sum(1 for qname, _ in dragonfly.local_queue if qname == queue_name)
