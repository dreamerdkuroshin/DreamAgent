"""
backend/core/execution_engine.py (Hardened)
Fix #27: run_task_background() now actually dispatches to the UltraAgent orchestrator.
"""
import asyncio
import logging
from backend.core.database import SessionLocal
from backend.services import task_service

logger = logging.getLogger(__name__)


async def run_task_background(task_id: int):
    """
    Background task runner — called by task_queue.enqueue_task().
    Fix #27: Actually executes the task via UltraAgent, stores result in DB.
    """
    db = SessionLocal()
    try:
        task = task_service.get_tasks(db)
        # Fetch specific task
        from backend.core import models
        task_obj = db.query(models.Task).filter(models.Task.id == task_id).first()
        if not task_obj:
            logger.warning(f"[execution_engine] Task {task_id} not found.")
            return

        task_service.update_task(db, task_id, {"status": "running"})
        logger.info(f"[execution_engine] Starting task {task_id}: {task_obj.title}")

        try:
            from backend.agents.ultra_agent import UltraAgent
            agent = UltraAgent(provider="auto")

            steps_log = []
            def noop_publish(event): steps_log.append(event)

            result = await agent.run(task_obj.title, noop_publish)
            task_service.update_task(db, task_id, {"status": "completed", "result": str(result)})
            logger.info(f"[execution_engine] Task {task_id} completed.")
        except Exception as e:
            logger.error(f"[execution_engine] Task {task_id} failed: {e}")
            task_service.update_task(db, task_id, {"status": "failed", "result": str(e)})
    finally:
        db.close()
