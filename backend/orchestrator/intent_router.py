"""
backend/orchestrator/intent_router.py

Abstract router interface + RouteDecision data model.
All routers (keyword, LLM, hybrid, cached) implement this contract.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RouteDecision:
    """Immutable routing verdict returned by any IntentRouter."""

    intent: str  # "builder" | "recall" | "update" | "continue" | "chat" | "tool" | "autonomous"
    confidence: float  # 0.0 – 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    # ── Convenience helpers ──────────────────────────────────────────────
    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.8

    def __repr__(self) -> str:
        return f"RouteDecision(intent={self.intent!r}, confidence={self.confidence:.2f})"


class IntentRouter(ABC):
    """
    Abstract base for all intent routers.

    Every implementation must accept a plain message string and an
    optional context dict (session_id, user_id, last_build, …) and
    return a RouteDecision.
    """

    @abstractmethod
    async def route(self, message: str, context: Optional[Dict[str, Any]] = None) -> RouteDecision:
        ...
