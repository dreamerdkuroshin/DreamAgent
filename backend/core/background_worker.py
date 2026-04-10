"""
backend/core/background_worker.py

Bounded background task queue to prevent event loop flooding.
Used for non-blocking operations like memory writes, telemetry, and logging.
"""
import asyncio
import logging
from typing import Callable, Coroutine, Any

logger = logging.getLogger(__name__)

class BackgroundWorker:
    def __init__(self, maxsize: int = 100):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.worker_task = None

    async def start(self):
        """Starts the background processing loop."""
        if not self.worker_task:
            self.worker_task = asyncio.create_task(self._run_worker())
            logger.info("BackgroundWorker loop started.")

    async def stop(self):
        """Stops the background worker cleanly."""
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            self.worker_task = None

    async def submit(self, coro: Coroutine[Any, Any, Any]):
        """Enqueues an async task, drops if queue is full to prevent OOM."""
        try:
            self.queue.put_nowait(coro)
        except asyncio.QueueFull:
            logger.error("[BackgroundWorker] Queue full! Dropping background task to protect event loop.")
            # We don't await queue.put because the caller (the orchestrator router) 
            # shouldn't be blocked if the system is backed up.
    
    async def _run_worker(self):
        while True:
            try:
                task_coro = await self.queue.get()
                try:
                    await task_coro
                except Exception as e:
                    logger.error(f"[BackgroundWorker] Unhandled error in background task: {e}")
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[BackgroundWorker] Loop error: {e}")

# Global singleton instance
bg_worker = BackgroundWorker()
