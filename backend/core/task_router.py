"""
backend/core/task_router.py

Intelligent multi-queue load balancer.
Classifies tasks by complexity and drops them into specialized queues.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, Any

from backend.core.dragonfly_manager import dragonfly
from backend.core.worker_state import WorkerState

logger = logging.getLogger(__name__)

# Queue Definitions
QUEUE_SIMPLE  = "tasks:simple"
QUEUE_MEDIUM  = "tasks:medium"
QUEUE_COMPLEX = "tasks:complex"


def classify_task(query: str, file_ids: str) -> str:
    """
    Determine execution difficulty based on query intent & payload size.
    Returns the appropriate queue name.
    """
    text = query.lower()
    word_count = len(text.split())

    # 1. Builder / creator intent → always complex regardless of word count
    #    "Build an X", "Create a Y", "Design a Z", "Launch a ..." etc.
    builder_keywords = {
        "build", "create", "design", "launch", "make", "develop", "generate",
        "set up", "start", "write", "plan", "deploy", "implement",
    }
    if any(k in text for k in builder_keywords):
        return QUEUE_COMPLEX

    # 2. Multi-day / multi-step plans → always complex
    if any(k in text for k in ["day 1", "day 2", "step 1", "phase 1", "week 1"]):
        return QUEUE_COMPLEX

    # 3. Coding / analytical tasks → complex
    heavy_keywords = {"code", "debug", "refactor", "analyze", "data", "report", "script", "api"}
    if any(k in text for k in heavy_keywords) and word_count > 6:
        return QUEUE_COMPLEX

    # 4. Files implies reading, embedding, or parsing — medium effort
    if file_ids:
        return QUEUE_MEDIUM

    # 5. Word-count based classification (fallback)
    if word_count <= 10:
        return QUEUE_SIMPLE
    elif word_count > 50 or len(query) > 500:
        return QUEUE_COMPLEX

    return QUEUE_MEDIUM



async def dispatch_task(task_payload: Dict[str, Any]) -> str:
    """
    Analyze incoming task, ensure idempotency, initialize its state machine, 
    and push to the appropriate local or distributed queue.
    """
    from backend.core.execution_mode import execution_state
    from backend.core.local_queue import local_queues
    import hashlib
    import time
    
    # 1. Idempotency Check
    raw_payload_str = json.dumps(task_payload, sort_keys=True)
    task_hash = hashlib.md5(raw_payload_str.encode()).hexdigest()
    
    if WorkerState.has_task(task_hash):
        logger.warning(f"⏩ [LoadBalancer] Deduplicating Task Payload Hash {task_hash}. Already in system.")
        return "duplicate"

    # Inject tracking bounds
    task_payload["task_id"] = task_hash
    task_payload["enqueued_at"] = time.time()
    
    query = task_payload.get("query", "")
    file_ids = task_payload.get("file_ids", "")

    queue_name = classify_task(query, file_ids)

    # 2. Inform the global State Machine
    WorkerState.initialize(task_hash, queue_name)

    # 3. Mode Selection logic
    payload_str = json.dumps(task_payload)
    client = dragonfly.get_client()

    mode = execution_state.mode
    if execution_state.force_redis_down:
        mode = "local"

    # Enforce Distributed Mode if Redis is active.
    # This ensures genuine queue persistence, job recovery, and enables horizontal worker scaling.
    use_distributed = (mode == "distributed") or (mode == "auto" and client is not None)

    if use_distributed:
        if not client:
            logger.warning("[LoadBalancer] Distributed mode but Redis unavailable — falling back to local.")
            local_queues.enqueue(queue_name, task_payload)
            return task_hash

        try:
            client.lpush(queue_name, payload_str)
            logger.info(f"🚀 [LoadBalancer] (DISTRIBUTED) Dispatched {task_hash[:8]}... => '{queue_name}' | query='{query[:30]}'")
        except Exception as e:
            logger.error(f"[LoadBalancer] Dragonfly dispatch failed for {task_hash}: {e}. Falling back to local.")
            local_queues.enqueue(queue_name, task_payload)
    else:
        # Local async queue — safe, instant pickup, no separate worker needed
        logger.info(f"🛠️ [LoadBalancer] (LOCAL) Dispatched {task_hash[:8]}... => '{queue_name}' | query='{query[:30]}'")
        local_queues.enqueue(queue_name, task_payload)

    return task_hash
