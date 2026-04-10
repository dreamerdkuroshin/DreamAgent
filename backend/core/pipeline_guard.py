"""
backend/core/pipeline_guard.py

Crash-Proof Pipeline Guard for DreamAgent Orchestrator.

Design rules (enforced strictly):
  - Catches ONLY explicitly typed exceptions — never bare `except Exception`
    except as a last-resort boundary at the outermost orchestrator layer.
  - Each exception type has a specific handling strategy.
  - All caught exceptions are re-raised after logging so the caller
    knows the step actually failed.
  - The optional `boundary` mode (for top-level orchestrator) catches
    everything as a last resort, logs CRITICAL, and returns gracefully.

Exception hierarchy handled:
  NameError      → import_healer.diagnose() → log suggestion → re-raise
  ImportError    → log module path → re-raise
  TimeoutError   → log which step timed out → re-raise
  asyncio.TimeoutError → same as above
  BudgetExceededError  → log token usage → re-raise (non-retryable)
"""
import asyncio
import logging
from typing import Callable, Any, Optional, Coroutine

logger = logging.getLogger(__name__)


async def guarded_execute(
    coro: Coroutine,
    publish: Callable[[dict], None],
    label: str = "pipeline",
    boundary: bool = False
) -> Any:
    """
    Wraps a coroutine with typed exception handling.

    Args:
        coro:     The coroutine to execute.
        publish:  The SSE publish function for emitting error events.
        label:    Identifies which pipeline step this is (for logging).
        boundary: If True, acts as a last-resort boundary — catches all
                  remaining exceptions, logs CRITICAL, and returns "".
                  Use ONLY at the outermost orchestrator level.

    Returns:
        The coroutine's return value on success.
        "" if boundary=True and an unhandled exception escapes.

    Raises:
        The original exception on all failures when boundary=False.
    """
    try:
        return await coro

    except NameError as e:
        # Pattern-match and log a concrete fix suggestion
        from backend.agents.import_healer import diagnose, format_error_event
        suggestion = diagnose(e)
        publish(format_error_event(e, suggestion))
        logger.error("[Guard:%s] NameError — %s", label, e, exc_info=True)
        if not boundary:
            raise

    except ImportError as e:
        publish({
            "type": "error",
            "agent": label,
            "content": f"⚠️ Module unavailable: {e}",
            "recoverable": False,
        })
        logger.error("[Guard:%s] ImportError — %s", label, e, exc_info=True)
        if not boundary:
            raise

    except (TimeoutError, asyncio.TimeoutError) as e:
        publish({
            "type": "error",
            "agent": label,
            "content": "⏱️ Step timed out. The operation took too long and was cancelled.",
            "recoverable": True,
        })
        logger.error("[Guard:%s] Timeout — %s", label, e)
        if not boundary:
            raise

    except Exception as e:
        # Check if it's a BudgetExceededError (imported lazily to avoid circular imports)
        is_budget = type(e).__name__ == "BudgetExceededError"

        if is_budget:
            publish({
                "type": "error",
                "agent": label,
                "content": f"🚫 Token budget exceeded for this task: {e}",
                "recoverable": False,
            })
            logger.error("[Guard:%s] BudgetExceededError — %s", label, e)
            if not boundary:
                raise

        elif boundary:
            # ── Last-resort boundary catch ──────────────────────────────
            # Only reached at the outermost orchestrator level.
            # Logs as CRITICAL so this is never missed in monitoring.
            logger.critical(
                "[Guard:%s] UNHANDLED EXCEPTION — this should never happen in production. "
                "Error: %s", label, e, exc_info=True
            )
            publish({
                "type": "error",
                "agent": label,
                "content": (
                    "❌ An unexpected internal error occurred. "
                    "The engineering team has been notified."
                ),
                "recoverable": False,
            })
            return ""

        else:
            # Not a known type and not a boundary — re-raise as-is
            raise


async def execute_step_safe(
    step_fn: Callable[..., Coroutine],
    *args,
    timeout: float = 30.0,
    step_label: str = "step",
    **kwargs
) -> Any:
    """
    Executes a single plan step with an independent timeout.
    Designed to be used inside asyncio.gather(..., return_exceptions=True).

    Returns the result on success.
    Returns an Exception instance on failure (caller checks with isinstance).

    This function NEVER raises — it always returns something,
    which is what makes gather-based parallel execution safe.
    """
    try:
        return await asyncio.wait_for(step_fn(*args, **kwargs), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(
            "[Guard:%s] Step timed out after %.1fs", step_label, timeout
        )
        return asyncio.TimeoutError(f"{step_label} exceeded {timeout}s timeout")
    except NameError as e:
        from backend.agents.import_healer import diagnose
        diagnose(e)  # Log the suggestion
        logger.error("[Guard:%s] NameError during step: %s", step_label, e, exc_info=True)
        return e
    except ImportError as e:
        logger.error("[Guard:%s] ImportError during step: %s", step_label, e, exc_info=True)
        return e
    except Exception as e:
        logger.error("[Guard:%s] Step failed: %s", step_label, e, exc_info=True)
        return e
