"""
backend/orchestrator/retry.py

Exponential-backoff retry with jitter.
Respects non-retryable error types and per-task retry policies.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Callable, Dict, Optional, Set, Tuple, Type

from backend.orchestrator.task_state import TaskContext, TaskState, BudgetExceededError

logger = logging.getLogger(__name__)

# ── Non-retryable exceptions (short-circuit immediately) ─────────────────
NON_RETRYABLE: Tuple[Type[Exception], ...] = (
    ValueError,        # bad input
    PermissionError,   # auth failures
    KeyError,          # missing config
    NotImplementedError,
    BudgetExceededError,  # token budget blown
)

# ── Per-intent retry policy ──────────────────────────────────────────────
# Maps intent → max retries.  Anything not listed defaults to 2.
RETRY_POLICY: Dict[str, int] = {
    "chat":       2,
    "builder":    2,
    "update":     1,
    "continue":   0,
    "recall":     1,
    "autonomous": 2,
    "tool":       1,   # tools may have side effects
}

BASE_DELAY = 0.5  # seconds


def get_max_retries(intent: str) -> int:
    """Look up the retry budget for a given intent."""
    return RETRY_POLICY.get(intent, 2)


async def with_retry(
    coro_factory: Callable[[], Any],
    task_ctx: TaskContext,
    publish: Optional[Callable[[Dict[str, Any]], None]] = None,
    max_retries: Optional[int] = None,
) -> Any:
    """
    Execute a coroutine with exponential-backoff retry.

    Args:
        coro_factory:  Callable that returns a fresh coroutine on each call.
        task_ctx:      TaskContext for state tracking.
        publish:       Optional SSE event publisher.
        max_retries:   Override retry count (defaults to task_ctx.max_retries).

    Returns:
        The result of the coroutine.

    Raises:
        The final exception if all retries are exhausted or error is non-retryable.
    """
    retries = max_retries if max_retries is not None else task_ctx.max_retries

    for attempt in range(retries + 1):
        try:
            task_ctx.attempt = attempt
            if task_ctx.state != TaskState.RUNNING:
                task_ctx.transition(TaskState.RUNNING)

            result = await coro_factory()

            task_ctx.transition(TaskState.COMPLETED)
            return result

        except NON_RETRYABLE as exc:
            # Non-retryable — fail immediately, don't waste time
            logger.error(
                "[Retry] Non-retryable error on attempt %d: %s",
                attempt + 1, exc,
            )
            task_ctx.error = str(exc)
            task_ctx.transition(TaskState.FAILED)
            raise

        except Exception as exc:
            is_last = attempt >= retries

            if is_last:
                logger.error(
                    "[Retry] Final attempt %d/%d failed: %s",
                    attempt + 1, retries + 1, exc,
                )
                task_ctx.error = str(exc)
                task_ctx.transition(TaskState.FAILED)
                if publish:
                    publish({
                        "type": "error",
                        "content": f"Task failed after {attempt + 1} attempt(s): {exc}",
                    })
                raise

            # Retryable — exponential backoff with jitter
            task_ctx.transition(TaskState.RETRYING)
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.3)
            logger.warning(
                "[Retry] Attempt %d/%d failed (%s). Retrying in %.2fs…",
                attempt + 1, retries + 1, exc, delay,
            )
            if publish:
                publish({
                    "type": "retry",
                    "attempt": attempt + 1,
                    "max_retries": retries,
                    "delay": round(delay, 2),
                    "content": f"⟳ Attempt {attempt + 1} failed. Retrying in {delay:.1f}s…",
                })
            await asyncio.sleep(delay)
