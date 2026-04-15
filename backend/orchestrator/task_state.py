"""
backend/orchestrator/task_state.py

Task lifecycle state machine with transition validation.
Lightweight Redis persistence when available.
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Dict, Optional

from backend.orchestrator.intent_router import RouteDecision

logger = logging.getLogger(__name__)


class TaskState(Enum):
    PENDING   = "pending"
    ROUTING   = "routing"
    RUNNING   = "running"
    PAUSED    = "paused"
    RETRYING  = "retrying"
    FAILED    = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


# Legal state transitions — anything not listed here is rejected
_VALID_TRANSITIONS: Dict[TaskState, set] = {
    TaskState.PENDING:   {TaskState.ROUTING, TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.ROUTING:   {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.RUNNING:   {TaskState.COMPLETED, TaskState.PAUSED, TaskState.RETRYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.PAUSED:    {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.RETRYING:  {TaskState.RUNNING, TaskState.PAUSED, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.FAILED:    set(),           # terminal
    TaskState.CANCELLED: set(),           # terminal
    TaskState.COMPLETED: set(),           # terminal
}


class InvalidTransitionError(Exception):
    """Raised when a state transition violates the state machine rules."""


class BudgetExceededError(Exception):
    """Raised when a task exceeds its token budget. Non-retryable."""


# Maximum tokens any single task may consume across all agents
MAX_TOKENS_PER_TASK = 100_000

CHECKPOINT_VERSION = "v1.3"


class TaskContext:
    """
    Tracks the full lifecycle of a single task.
    Thread-safe state transitions with optional Redis persistence.
    """

    __slots__ = (
        "task_id", "user_id", "state", "attempt", "max_retries",
        "created_at", "updated_at", "error", "route_decision",
        "token_usage", "checkpoint", "_redis",
    )

    def __init__(
        self,
        task_id: str,
        user_id: str = "local_user",
        max_retries: int = 2,
        redis_conn=None,
    ):
        self.task_id = task_id
        self.user_id = user_id
        self.state = TaskState.PENDING
        self.attempt = 0
        self.max_retries = max_retries
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.error: Optional[str] = None
        self.token_usage: int = 0
        self.route_decision: Optional[RouteDecision] = None
        self.checkpoint: Dict[str, Any] = {"completed_steps": {}, "original_query": "", "version": CHECKPOINT_VERSION}
        self._redis = redis_conn

    # ── State transitions ────────────────────────────────────────────────
    def transition(self, new_state: TaskState) -> None:
        """
        Move to a new state.  Raises InvalidTransitionError for illegal moves.
        Persists lightweight state to Redis when available.
        """
        allowed = _VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition {self.state.value} → {new_state.value} "
                f"(task={self.task_id})"
            )

        old = self.state
        self.state = new_state
        self.updated_at = time.time()

        logger.info(
            "[TaskState] %s → %s  task=%s user=%s attempt=%d",
            old.value, new_state.value, self.task_id, self.user_id, self.attempt,
        )

        self.log_transition(old, new_state, f"Transition from {old.value} to {new_state.value}")
        self._persist()

    def log_transition(self, old_state: TaskState, new_state: TaskState, message: str) -> None:
        """Pushes an explicit, immutable log entry to the Observability trail."""
        if not self._redis: return
        import json
        log_entry = {
            "task_id": self.task_id,
            "old_state": old_state.value if old_state else None,
            "new_state": new_state.value if new_state else None,
            "timestamp": time.time(),
            "message": message
        }
        try:
            log_key = f"tasks:{self.task_id}:state_log"
            self._redis.rpush(log_key, json.dumps(log_entry))
            
            # Log compaction: trim if > 100 to prevent silent memory explosion
            if self._redis.llen(log_key) > 100:
                self._redis.ltrim(log_key, -50, -1)
                self._redis.rpush(log_key, json.dumps({"message": "[... Compacted old logs ...]", "timestamp": time.time()}))
            
            # Optional TTL for cleanup
            self._redis.expire(log_key, 604800) # 7 days
        except Exception as e:
            logger.debug(f"[TaskState] Failed to log state transition: {e}")

    # ── Convenience ──────────────────────────────────────────────────────
    @property
    def is_terminal(self) -> bool:
        return self.state in (TaskState.FAILED, TaskState.CANCELLED, TaskState.COMPLETED)

    @property
    def elapsed_ms(self) -> int:
        return int((time.time() - self.created_at) * 1000)

    @property
    def is_zombie(self) -> bool:
        """Returns True if task is PAUSED or RETRYING but hasn't had activity in 24h."""
        if self.state in (TaskState.PAUSED, TaskState.RETRYING):
            return (time.time() - self.updated_at) > 86400  # 24 hours
        return False

    def track_tokens(self, tokens: int) -> None:
        """Add tokens and enforce budget. Raises BudgetExceededError if exceeded."""
        self.token_usage += tokens
        if self.token_usage > MAX_TOKENS_PER_TASK:
            self.error = f"Token budget exceeded: {self.token_usage}/{MAX_TOKENS_PER_TASK}"
            logger.warning(
                "[TaskState] Budget exceeded: %d/%d  task=%s",
                self.token_usage, MAX_TOKENS_PER_TASK, self.task_id,
            )
            raise BudgetExceededError(self.error)

    def to_dict(self) -> Dict[str, Any]:
        """Lightweight dict for Redis / SSE serialization."""
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "attempt": self.attempt,
            "updated_at": self.updated_at,
            "error": self.error,
            "token_usage": self.token_usage,
            "checkpoint": self.checkpoint,
        }

    # ── Redis persistence (lightweight — no full RouteDecision) ──────────
    def _persist(self) -> None:
        if not self._redis:
            return
        try:
            import json
            key = f"task:{self.task_id}:state"
            self._redis.setex(key, 3600, json.dumps(self.to_dict()))
        except Exception as exc:
            logger.debug("[TaskState] Redis persist failed: %s", exc)
