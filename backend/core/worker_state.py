"""
backend/core/worker_state.py

Abstract state tracker for task lifecycle. 
Eliminates data drift between Dev and Prod by utilizing an explicit 
LocalStateStore if the application is running in fallback/local mode.
"""
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from backend.core.dragonfly_manager import dragonfly
from backend.core.execution_mode import execution_state

logger = logging.getLogger(__name__)

# Real Orchestrator Lifecycle States
PENDING    = "pending"
RUNNING    = "running"
SUCCESS    = "success"
FAILED     = "failed"
RETRYING   = "retrying"

MAX_RETRIES = 3
STUCK_TIMEOUT_SECONDS = 600  # 10 minutes


class StateStore(ABC):
    @abstractmethod
    def initialize(self, task_id: str, queue_name: str) -> None: ...
    @abstractmethod
    def transition(self, task_id: str, new_status: str, error: str = "") -> None: ...
    @abstractmethod
    def get_state(self, task_id: str) -> Optional[Dict[str, str]]: ...
    @abstractmethod
    def increment_attempt(self, task_id: str) -> int: ...
    @abstractmethod
    def has_task(self, task_id: str) -> bool: ...


class LocalStateStore(StateStore):
    """In-memory dictionary to mimic Redis Hashes perfectly in Dev Mode."""
    def __init__(self):
        self._memory: Dict[str, Dict[str, Any]] = {}

    def initialize(self, task_id: str, queue_name: str) -> None:
        self._memory[task_id] = {
            "status": PENDING,
            "queue": queue_name,
            "attempts": 0,
            "created_at": time.time(),
            "last_update": time.time(),
        }

    def transition(self, task_id: str, new_status: str, error: str = "") -> None:
        if task_id not in self._memory:
            return
        self._memory[task_id]["status"] = new_status
        self._memory[task_id]["last_update"] = time.time()
        if error:
            self._memory[task_id]["error"] = error
        logger.debug(f"[LocalState] Task {task_id} => {new_status}")

    def get_state(self, task_id: str) -> Optional[Dict[str, str]]:
        return self._memory.get(task_id)

    def increment_attempt(self, task_id: str) -> int:
        if task_id not in self._memory:
            return 1
        self._memory[task_id]["attempts"] += 1
        self._memory[task_id]["last_update"] = time.time()
        return self._memory[task_id]["attempts"]

    def has_task(self, task_id: str) -> bool:
        return task_id in self._memory


class RedisStateStore(StateStore):
    """Production mode tracker using Dragonfly Hash fields."""
    def _key(self, task_id: str) -> str:
        return f"task_state:{task_id}"

    def initialize(self, task_id: str, queue_name: str) -> None:
        client = dragonfly.get_client()
        if not client: return
        client.hset(self._key(task_id), mapping={
            "status": PENDING,
            "queue": queue_name,
            "attempts": 0,
            "created_at": time.time(),
            "last_update": time.time(),
        })
        client.expire(self._key(task_id), 86400 * 7)

    def transition(self, task_id: str, new_status: str, error: str = "") -> None:
        client = dragonfly.get_client()
        if not client: return
        mapping = {"status": new_status, "last_update": time.time()}
        if error: mapping["error"] = error
        client.hset(self._key(task_id), mapping=mapping)
        logger.debug(f"[RedisState] Task {task_id} => {new_status}")

    def get_state(self, task_id: str) -> Optional[Dict[str, str]]:
        client = dragonfly.get_client()
        if not client: return None
        raw = client.hgetall(self._key(task_id))
        return raw if raw else None

    def increment_attempt(self, task_id: str) -> int:
        client = dragonfly.get_client()
        if not client: return 1
        attempts = client.hincrby(self._key(task_id), "attempts", 1)
        client.hset(self._key(task_id), "last_update", time.time())
        return int(attempts)

    def has_task(self, task_id: str) -> bool:
        client = dragonfly.get_client()
        if not client: return False
        return client.exists(self._key(task_id)) > 0


class WorkerStateProxy:
    """Delegates to the correct Store depending on the active execution mode."""
    def __init__(self):
        self._local = LocalStateStore()
        self._redis = RedisStateStore()

    @property
    def _proxy(self) -> StateStore:
        if execution_state.mode == "local" or execution_state.force_redis_down or not dragonfly.is_connected():
            return self._local
        return self._redis

    def initialize(self, task_id: str, queue_name: str):
        self._proxy.initialize(task_id, queue_name)

    def transition(self, task_id: str, new_status: str, error: str = ""):
        self._proxy.transition(task_id, new_status, error)

    def get_state(self, task_id: str) -> Optional[Dict[str, str]]:
        return self._proxy.get_state(task_id)

    def increment_attempt(self, task_id: str) -> int:
        return self._proxy.increment_attempt(task_id)

    def has_task(self, task_id: str) -> bool:
        return self._proxy.has_task(task_id)

# Global unified state access point
WorkerState = WorkerStateProxy()
