"""
backend/worker_local.py

Spawned internally by main.py ONLY when EXECUTION_MODE is 'local', or 'auto' 
when Redis is unreachable. It mimics worker.py entirely, preventing Dev/Prod logic drift.
"""
import asyncio
import time
import logging

from backend.core.worker_state import WorkerState, PENDING, RUNNING, SUCCESS, FAILED, RETRYING, MAX_RETRIES
from backend.core.local_queue import local_queues
from backend.core.execution_mode import execution_state
from backend.api.chat_worker import background_agent_loop

logger = logging.getLogger(__name__)

WORKER_RUNNING = False


async def local_worker_loop():
    """
    Blocks naturally via asyncio.Queue.get(). It checks priorities explicitly:
    Complex -> Medium -> Simple.
    """
    global WORKER_RUNNING
    logger.info("👷 [Local Worker] Instantiated. Providing execution logic mimicking Dragonfly nodes.")
    
    while True:
        try:
            # Multi-Queue Priority Polling
            task_payload = None
            queue_name = None
            
            # Non-blocking peek
            if not local_queues.complex.empty():
                task_payload = local_queues.complex.get_nowait()
                queue_name = "tasks:complex"
            elif not local_queues.medium.empty():
                task_payload = local_queues.medium.get_nowait()
                queue_name = "tasks:medium"
            elif not local_queues.simple.empty():
                task_payload = local_queues.simple.get_nowait()
                queue_name = "tasks:simple"
            else:
                # Instead of busy-looping over `.empty()`, wait exactly on the lowest queue, 
                # but if anything hits `medium` in the meantime, it won't be picked up instantly.
                # A robust trick in asyncio is wait(return_when=FIRST_COMPLETED).
                # For simplicity here: small idle wait.
                await asyncio.sleep(0.1)
                continue

            # Record Wait latency
            task_id = task_payload.get("task_id", "")
            enqueued_time = task_payload.get("enqueued_at", time.time())
            wait_time = time.time() - enqueued_time
            
            logger.info(f"⚙️ [Local Worker] Picked up {task_id} from {queue_name} (Wait: {wait_time:.2f}s)")
            
            execution_state.increment_active()
            WorkerState.transition(task_id, RUNNING)
            start_time = time.time()
            
            try:
                # Extract
                query = task_payload.get("query", "")
                convo_id = task_payload.get("convo_id")
                provider = task_payload.get("provider", "auto")
                model = task_payload.get("model", "")
                file_ids = task_payload.get("file_ids", "")

                # Execute safely with Hard Timeout
                is_success = False
                for attempt in range(MAX_RETRIES):
                    try:
                        await asyncio.wait_for(
                            background_agent_loop(
                                query=query, 
                                task_id=task_id, 
                                convo_id=convo_id, 
                                provider=provider, 
                                model=model, 
                                file_ids=file_ids
                            ), 
                            timeout=60.0  # Reduced to 60s to match dragonfly worker
                        )
                        is_success = True
                        break  # Success, exit retry loop

                    except asyncio.TimeoutError:
                        logger.error(f"⏱️ [Local Worker] Task {task_id} TIMEOUT (Attempt {attempt+1}/{MAX_RETRIES})")
                        if attempt < MAX_RETRIES - 1:
                            WorkerState.transition(task_id, RETRYING, error="Execution Timeout")
                            execution_state.increment_retry()
                            await asyncio.sleep(1)

                    except Exception as e:
                        logger.error(f"❌ [Local Worker] Task {task_id} CRASH (Attempt {attempt+1}/{MAX_RETRIES}): {e}")
                        if attempt < MAX_RETRIES - 1:
                            WorkerState.transition(task_id, RETRYING, error=str(e))
                            execution_state.increment_retry()
                            await asyncio.sleep(1)
                
                # Post-Execution state shift & Metrics
                exec_time = time.time() - start_time
                if is_success:
                    WorkerState.transition(task_id, SUCCESS)
                    execution_state.record_completion(wait_time, exec_time, failed=False)
                    logger.info(f"✅ [Local Worker] Completed {task_id} (Exec: {exec_time:.2f}s)")
                else:
                    WorkerState.transition(task_id, FAILED, error="Exhausted all retries")
                    execution_state.record_completion(wait_time, exec_time, failed=True)
                    
                    logger.critical(f"💀 [Local Worker] Task {task_id} Dropping to Dead Letter Queue (DLQ)")
                    local_queues.dead_letter.append(task_payload)
            
            finally:
                # Guarantee queue task marked off
                if queue_name == "tasks:complex": local_queues.complex.task_done()
                if queue_name == "tasks:medium":  local_queues.medium.task_done()
                if queue_name == "tasks:simple":  local_queues.simple.task_done()

        except Exception as global_e:
            logger.error(f"[Local Worker] Global Fatal Error in polling loop: {global_e}")
            await asyncio.sleep(2)


def start_local_worker():
    """Triggered in FASTAPI lifespan — singleton guarantee."""
    global WORKER_RUNNING
    if not WORKER_RUNNING:
        asyncio.create_task(local_worker_loop(), name="local-queue-worker")
        WORKER_RUNNING = True
