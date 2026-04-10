"""
backend/core/state_manager.py
Manages the execution state of running tasks in Dragonfly or in-memory.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskState:
    task_id: str
    status: str = "pending"
    current_step: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[str] = None


class StateManager:
    def __init__(self, redis_conn=None):
        self._redis = redis_conn
        self._memory: Dict[str, Dict] = {}

    def save_state(self, state: TaskState):
        data = {
            "task_id": state.task_id,
            "status": state.status,
            "current_step": state.current_step,
            "history": state.history,
            "result": state.result,
        }
        if self._redis:
            try:
                self._redis.set(f"state:{state.task_id}", json.dumps(data))
                return
            except Exception as e:
                logger.warning(f"Dragonfly state save failed: {e}")
        self._memory[state.task_id] = data

    def load_state(self, task_id: str) -> TaskState:
        data = None
        if self._redis:
            try:
                raw = self._redis.get(f"state:{task_id}")
                if raw:
                    data = json.loads(raw)
            except Exception as e:
                logger.warning(f"Dragonfly state load failed: {e}")
        if data is None:
            data = self._memory.get(task_id, {"task_id": task_id})
        return TaskState(
            task_id=data.get("task_id", task_id),
            status=data.get("status", "pending"),
            current_step=data.get("current_step", 0),
            history=data.get("history", []),
            result=data.get("result"),
        )
