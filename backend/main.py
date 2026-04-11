import os
import logging
import logging.handlers
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables early
load_dotenv()

# ─── Centralized Logging Setup ────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

_fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=_fmt,
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)
# ──────────────────────────────────────────────────────────────────────────────

from backend.api.router import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.core.database import engine, Base
    import backend.core.models  # noqa: ensure models are registered
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified.")

    # Start Dragonfly Self-Healing Monitor
    from backend.core.dragonfly_manager import dragonfly
    await dragonfly.connect()
    dragonfly.start_monitor()

    # Always attempt to start the Local CPU Async Worker safely 
    # (The worker automatically ignores execution if mode is distributed)
    from backend.worker_local import start_local_worker
    start_local_worker()

    # Start the fast orchestrator bounded background queue
    from backend.core.background_worker import bg_worker
    await bg_worker.start()

    # Watchdog for stuck Distributed Worker Tasks
    import asyncio
    import json
    import time
    from backend.core.worker_state import WorkerState, STUCK_TIMEOUT_SECONDS, PENDING

    async def recover_stuck_tasks():
        while True:
            await asyncio.sleep(60) # Run every 60 seconds
            client = dragonfly.get_client()
            if not client:
                continue

            try:
                # Get all items in the processing queue
                tasks_raw = client.lrange("tasks:processing", 0, -1)
                for raw_task in tasks_raw:
                    task_payload = json.loads(raw_task)
                    task_id = task_payload.get("task_id", "")
                    
                    state = WorkerState.get_state(task_id)
                    if state:
                        last_update = float(state.get("last_update", 0))
                        # If untouched for 10 minutes:
                        if time.time() - last_update > STUCK_TIMEOUT_SECONDS:
                            logger.error(f"🚨 [Watchdog] Detected stuck task {task_id}. Re-queueing!")
                            orig_queue = state.get("queue", "tasks:medium")
                            
                            # Increment attempt and push back
                            WorkerState.increment_attempt(task_id)
                            WorkerState.transition(task_id, PENDING, error="Recovered by watchdog (stuck)")
                            
                            client.lrem("tasks:processing", 1, raw_task)
                            client.lpush(orig_queue, raw_task)
            except Exception as e:
                logger.warning(f"[Watchdog] Recovery failed this tick: {e}")

    asyncio.create_task(recover_stuck_tasks(), name="stuck-task-watchdog")

    yield
    
    # Teardown
    await bg_worker.stop()


app = FastAPI(
    title="DreamAgent API",
    description="DreamAgent backend — v2 structured architecture",
    version="2.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {response.status_code} {request.url.path}")
    return response


import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    exc_type = type(exc).__name__
    module_name = getattr(exc, '__module__', 'BuiltIn')
    failure_stage = f"{request.method} {request.url.path}"
    exact_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    
    logger.error(f"❌ [Uncaught Fault in {module_name}]\nStage: {failure_stage}\nType: {exc_type}\nTrace:\n{exact_trace}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False, 
            "error": "Critical System Failure Diagnosed",
            "diagnostics": {
                "module": module_name,
                "stage": failure_stage,
                "exception_type": exc_type,
                "exact_trace": exact_trace
            }
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {"success": True, "data": {"status": "DreamAgent backend is running", "version": "2.0.0"}, "error": None}


@app.get("/healthz")
def healthz():
    try:
        from backend.core.dragonfly_manager import dragonfly
        df_status = dragonfly.status()
    except Exception:
        df_status = {"mode": "unknown", "error": "dragonfly module not loaded"}

    return {
        "success": True, 
        "data": {"status": "ok", "dragonfly": df_status}, 
        "error": None
    }


@app.get("/api/system-status")
async def system_status():
    from backend.core.dragonfly_manager import dragonfly
    from backend.core.execution_mode import execution_state
    from backend.core.local_queue import local_queues

    metrics = execution_state.get_summary()
    
    # Mode Evaluation
    active_mode = "local" if not dragonfly.is_connected() or execution_state.force_redis_down else "distributed"
    
    if active_mode == "local":
        q_simple  = local_queues.simple.qsize()
        q_medium  = local_queues.medium.qsize()
        q_complex = local_queues.complex.qsize()
        q_proc    = 1 if metrics.get("active_tasks", 0) > 0 else 0
        q_dead    = len(local_queues.dead_letter)
        q_comp    = metrics.get("completed_tasks", 0)
        q_fail    = metrics.get("failed_tasks", 0)
    else:
        client = dragonfly.get_client()
        if client:
            try:
                q_simple  = client.llen("tasks:simple")
                q_medium  = client.llen("tasks:medium")
                q_complex = client.llen("tasks:complex")
                q_proc    = client.llen("tasks:processing")
                q_fail    = client.llen("tasks:failed")
                q_dead    = client.llen("tasks:dead")
                q_comp    = client.llen("tasks:completed")
            except Exception:
                q_simple = q_medium = q_complex = q_proc = q_fail = q_dead = q_comp = 0
        else:
            q_simple = q_medium = q_complex = q_proc = q_fail = q_dead = q_comp = 0

    return {
        "success": True,
        "mode": active_mode,
        "chaos_switch": execution_state.force_redis_down,
        "metrics": metrics,
        "queues": {
            "pending_simple": q_simple,
            "pending_medium": q_medium,
            "pending_complex": q_complex,
            "processing": q_proc,
            "failed": q_fail,
            "dead_letter": q_dead,
            "completed_log": q_comp,
            "TOTAL_BACKLOG": q_simple + q_medium + q_complex
        }
    }


@app.post("/simulate/redis-down")
async def simulate_redis_down(enable: bool = True):
    """Chaos switch to forcefully sever the Distributed execution layer and fallback to Local queue."""
    from backend.core.execution_mode import execution_state
    
    execution_state.set_chaos_mode(enable)
    return {
        "success": True, 
        "message": "Chaos mode activated: Fallback processing triggered" if enable else "Chaos mode disabled.",
        "mode": execution_state.mode
    }
