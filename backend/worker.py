import sys
import os
from pathlib import Path

# Fix: Add the project root to sys.path so 'from backend...' works
# even when running this file directly as a script.
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import asyncio
import argparse
import json
import logging
import signal
import uuid
import pkgutil 

# ── Ensure the Django/FastAPI ORMs start properly in a detached worker process ──
try:
    from sqlalchemy import text
    from backend.core.database import SessionLocal
    # Quick DB test 
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    from backend.core.dragonfly_manager import dragonfly
except Exception as e:
    print(f"Failed to bootstrap worker environment: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [WORKER] %(message)s")
logger = logging.getLogger(__name__)

# Test: Auto-reload trigger
import uuid
from backend.core.worker_state import WorkerState, PENDING, RUNNING, SUCCESS, FAILED, RETRYING, MAX_RETRIES

# The heavy execution block
from backend.api.chat_worker import background_agent_loop


class DistributedWorker:
    def __init__(self, queues: list[str], worker_id: str):
        self.queues = queues
        self.worker_id = worker_id
        self.is_shutting_down = False
        self.client = dragonfly.get_client()

    def _setup_graceful_shutdown(self):
        def sig_handler(signum, frame):
            logger.info(f"🛑 [Worker {self.worker_id}] Received shutdown signal. Emptying queues safely...")
            self.is_shutting_down = True
            
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

    async def _execute_task_pipeline(self, task_payload: dict, queue_name: str, raw_task_json: str) -> None:
        """Run the actual heavy LLM multi-agent loop."""
        task_id = task_payload.get("task_id", "unknown")
        logger.info(f"⚙️  [Worker {self.worker_id}] Executing Task: {task_id}")

        # 1. Start execution -> Shift state Machine
        WorkerState.transition(task_id, RUNNING)
        
        # In Redis: move it out of pending, into processing explicitly
        # We did this atomically with brpoplpush, but we need to track it manually if the local dragonfly manager pop logic was used
        self.client.lpush("tasks:processing", raw_task_json)

        try:
            # 2. Extract arguments
            query = task_payload.get("query", "")
            convo_id = task_payload.get("convo_id")
            provider = task_payload.get("provider", "auto")
            model = task_payload.get("model", "")
            file_ids = task_payload.get("file_ids", "")

            # explicit redis status "running" 
            self.client.set(f"task:{task_id}:status", "running")

            # 3. Blocking heavy workload with Timeout Watchdog!
            await asyncio.wait_for(background_agent_loop(
                query=query, 
                task_id=task_id, 
                convo_id=convo_id, 
                provider=provider, 
                model=model, 
                file_ids=file_ids
            ), timeout=60.0)

            # 4. Success -> Mark Complete State
            WorkerState.transition(task_id, SUCCESS)
            self.client.set(f"task:{task_id}:status", "completed")
            
            # 5. Move task from processing queue to completed log 
            self.client.lpush("tasks:completed", json.dumps({
                "task_id": task_id,
                "status": "success",
                "worker": self.worker_id
            }))
            
            logger.info(f"✅ [Worker {self.worker_id}] Completed Task: {task_id}")

        except asyncio.TimeoutError:
            logger.error(f"⏱️ [Worker {self.worker_id}] Task {task_id} TIMED OUT (>60s).")
            self.client.set(f"task:{task_id}:status", "failed")
            WorkerState.transition(task_id, FAILED, error="Timeout exceeded")
            self.client.rpush(f"task:{task_id}:events", json.dumps({"type": "error", "content": "Execution timed out (60s)."}))
            self.client.lpush("tasks:dead", json.dumps({"task": task_payload, "error": "Timeout exceeded"}))
            
        except Exception as e:
            logger.error(f"❌ [Worker {self.worker_id}] Task {task_id} FAILED: {e}")
            self.client.set(f"task:{task_id}:status", "failed")
            
            # Retry mechanism
            attempts = WorkerState.increment_attempt(task_id)
            
            if attempts <= MAX_RETRIES:
                logger.warning(f"🔄 [Worker {self.worker_id}] Retrying Task {task_id} (Attempt {attempts}/{MAX_RETRIES})")
                WorkerState.transition(task_id, RETRYING, error=str(e))
                self.client.lpush(queue_name, raw_task_json)
            else:
                logger.error(f"💀 [Worker {self.worker_id}] Task {task_id} FAILED (Exhausted {MAX_RETRIES} Retries). Dropping into dead-letter.")
                WorkerState.transition(task_id, FAILED, error=str(e))
                self.client.lpush("tasks:dead", json.dumps({
                    "task": task_payload,
                    "error": str(e)
                }))
        finally:
            # Guarantee queue cleanup regardless of outcome
            try:
                self.client.lrem("tasks:processing", 1, raw_task_json)
            except Exception as e:
                logger.error(f"[Worker] Final queue cleanup failed: {e}")


    async def start_loop(self):
        """Infinite polling loop against predefined queues."""
        self._setup_graceful_shutdown()
        
        # Keep waiting until we're connected to Dragonfly (Fallback memory mode doesn't work for horizontal scaling!)
        while not dragonfly.is_connected():
            logger.warning(f"⏳ [Worker {self.worker_id}] Waiting for Dragonfly Database to boot up before pulling tasks...")
            await dragonfly.connect()
            await asyncio.sleep(5)
            self.client = dragonfly.get_client()

        logger.info(f"🚀 [Worker {self.worker_id}] Connected. Listening across queues -> {self.queues}")

        if os.environ.get("EXECUTION_MODE", "auto").lower() == "local":
            logger.error(f"🚫 [Worker {self.worker_id}] Halting. EXECUTION_MODE is 'local'.")
            return

        while not self.is_shutting_down:
            try:
                # 1. Block for picking up a task. Prioritize queues sequentially high -> low.
                # brpop accepts multiple keys, so passing self.queues works natively for prioritization!
                popped = self.client.brpop(self.queues, timeout=5)

                if popped:
                    queue_name, raw_task_json = popped
                    task_payload = json.loads(raw_task_json)
                    
                    # Offload the execution to prevent blocking the worker event loop entirely?
                    # No, typically 1 worker pod handles 1 concurrency limit unless asyncio.create_task is used
                    # For safety + proper horizontal execution testing, we will await it sequentially in THIS worker instance.
                    await self._execute_task_pipeline(task_payload, queue_name.decode('utf-8') if isinstance(queue_name, bytes) else queue_name, raw_task_json)
                    
            except Exception as e:
                if not self.is_shutting_down:
                    logger.error(f"🔥 [Worker {self.worker_id}] Global Loop Error: {e}")
                    await asyncio.sleep(2)  # Backoff

        logger.info(f"👋 [Worker {self.worker_id}] Gracefully Terminated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start a DreamAgent Distributed LLM Worker.")
    parser.add_argument("--queues", type=str, default="tasks:complex,tasks:medium,tasks:simple", help="Comma-separated queue names to block on in descending priority order.")
    parser.add_argument("--id", type=str, default=None, help="Specific ID for this worker pod (randomized if none)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload worker when code changes (for development)")
    args = parser.parse_args()

    q_list = [q.strip() for q in args.queues.split(",")]
    worker_id = args.id if args.id else f"worker-{str(uuid.uuid4())[:8]}"

    if getattr(args, "reload", False):
        import subprocess
        from pathlib import Path
        try:
            from watchfiles import watch
        except ImportError:
            logger.error("❌ Cannot use --reload because 'watchfiles' is not installed.")
            sys.exit(1)

        watch_dir = Path(__file__).parent
        logger.info(f"🔄 [Reloader] Monitoring {watch_dir} for changes...")

        # Construct the same command but without --reload to avoid infinite spawning
        cmd = [sys.executable] + [arg for arg in sys.argv if arg != "--reload"]

        while True:
            process = subprocess.Popen(cmd)
            try:
                for changes in watch(watch_dir):
                    logger.warning("🛠️  [Reloader] Detected code changes. Restarting Distributed Worker...")
                    process.terminate()
                    process.wait(timeout=5)
                    if process.poll() is None:
                        process.kill()
                    break  # Break out of watchfiles loop to spawn a new process
            except KeyboardInterrupt:
                process.terminate()
                sys.exit(0)
    else:
        # Normal execution
        worker = DistributedWorker(queues=q_list, worker_id=worker_id)
        try:
            asyncio.run(worker.start_loop())
        except KeyboardInterrupt:
            logger.info("Main Thread Interrupted.")
