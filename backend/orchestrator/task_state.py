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
    RETRYING  = "retrying"
    FAILED    = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


# Legal state transitions — anything not listed here is rejected
_VALID_TRANSITIONS: Dict[TaskState, set] = {
    TaskState.PENDING:   {TaskState.ROUTING, TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.ROUTING:   {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.RUNNING:   {TaskState.COMPLETED, TaskState.RETRYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.RETRYING:  {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED},
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


class TaskContext:
    """
    Tracks the full lifecycle of a single task.
    Thread-safe state transitions with optional Redis persistence.
    """

    __slots__ = (
        "task_id", "user_id", "state", "attempt", "max_retries",
        "created_at", "updated_at", "error", "route_decision",
        "token_usage", "_redis",
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

        self._persist()

    # ── Convenience ──────────────────────────────────────────────────────
    @property
    def is_terminal(self) -> bool:
        return self.state in (TaskState.FAILED, TaskState.CANCELLED, TaskState.COMPLETED)

    @property
    def elapsed_ms(self) -> int:
        return int((time.time() - self.created_at) * 1000)

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
