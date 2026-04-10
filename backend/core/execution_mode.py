"""
backend/core/execution_mode.py

Global singleton managing Dev vs Prod Execution behaviors.
It tracks the active Execution Mode, the Chaos Testing Switch, and system-wide metrics.
"""
import os
import time
import logging

logger = logging.getLogger(__name__)

class ExecutionState:
    def __init__(self):
        # Modes: "auto" / "local" / "distributed"
        self.mode = os.environ.get("EXECUTION_MODE", "auto").lower()
        self.force_redis_down = False
        
        # Real-time Metrics (Primarily driven by the local fallback queue loop)
        self.metrics = {
            "active": 0,
            "completed": 0,
            "failed": 0,
            "total_execution_time": 0.0,
            "total_wait_time": 0.0,
            "retries": 0
        }

    def set_chaos_mode(self, down: bool):
        """Enable or disable the Redis Force-Disconnect Simulation."""
        self.force_redis_down = down
        if down:
            logger.warning("🚨 CHAOS SWITCH ENABLED! Simulating Dragonfly outage...")
        else:
            logger.info("✅ CHAOS SWITCH OFF. Restoring normal Dragonfly checks...")

    def record_completion(self, wait_time: float, exec_time: float, failed: bool = False):
        """Update unified metrics upon task finality."""
        if failed:
            self.metrics["failed"] += 1
        else:
            self.metrics["completed"] += 1
            
        self.metrics["total_wait_time"] += wait_time
        self.metrics["total_execution_time"] += exec_time
        if self.metrics["active"] > 0:
            self.metrics["active"] -= 1

    def increment_active(self):
        self.metrics["active"] += 1

    def increment_retry(self):
        self.metrics["retries"] += 1

    def get_summary(self) -> dict:
        total = self.metrics["completed"] + self.metrics["failed"]
        avg_exec = round(self.metrics["total_execution_time"] / total, 3) if total > 0 else 0.0
        avg_wait = round(self.metrics["total_wait_time"] / total, 3) if total > 0 else 0.0
        
        return {
            "mode": "local" if self.force_redis_down or self.mode == "local" else self.mode,
            "chaos_switch_active": self.force_redis_down,
            "active_tasks": self.metrics["active"],
            "completed_tasks": self.metrics["completed"],
            "failed_tasks": self.metrics["failed"],
            "avg_execution_time_sec": avg_exec,
            "avg_queue_wait_sec": avg_wait,
            "retries": self.metrics["retries"]
        }


# Global Singleton
execution_state = ExecutionState()
