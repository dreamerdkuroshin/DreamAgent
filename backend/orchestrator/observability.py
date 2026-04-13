"""
backend/orchestrator/observability.py

Structured contextual logger that attaches task/user metadata
to every log line for production debugging.

Output:
  [2026-04-01T21:50:00] ERROR | task_id=abc123 user_id=local_user stage=router | msg
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("dreamagent.orchestrator")

class TaskLogger:
    """
    Context-aware logger.
    Every log call automatically attaches task_id, user_id, and optional stage.
    """

    __slots__ = ("_base_extra",)

    def __init__(self, task_id: str, user_id: str = "local_user", intent: str = "unknown"):
        self._base_extra: Dict[str, Any] = {
            "task_id": task_id,
            "user_id": user_id,
            "intent": intent,
        }

    def _merge(self, stage: str = "", **kwargs: Any) -> Dict[str, Any]:
        extra = {**self._base_extra, **kwargs}
        if stage:
            extra["stage"] = stage
        return extra

    def _fmt(self, msg: str, extra: Dict[str, Any]) -> str:
        """Format extra fields into a human-readable prefix."""
        parts = " ".join(f"{k}={v}" for k, v in extra.items() if v)
        return f"[{parts}] {msg}"

    # ── Public API ───────────────────────────────────────────────────────
    def info(self, msg: str, stage: str = "", **kwargs: Any) -> None:
        extra = self._merge(stage, **kwargs)
        logger.info(self._fmt(msg, extra))

    def warning(self, msg: str, stage: str = "", **kwargs: Any) -> None:
        extra = self._merge(stage, **kwargs)
        logger.warning(self._fmt(msg, extra))

    def error(self, msg: str, stage: str = "", **kwargs: Any) -> None:
        extra = self._merge(stage, **kwargs)
        logger.error(self._fmt(msg, extra))

    def debug(self, msg: str, stage: str = "", **kwargs: Any) -> None:
        extra = self._merge(stage, **kwargs)
        logger.debug(self._fmt(msg, extra))
