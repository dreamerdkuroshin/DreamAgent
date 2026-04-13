"""
backend/orchestrator/keyword_router.py

Thin wrapper that delegates to priority_router.detect_intent()
as the SINGLE source of truth. Zero regex duplication here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.orchestrator.intent_router import IntentRouter, RouteDecision
from backend.orchestrator.priority_router import detect_intent_with_confidence

logger = logging.getLogger(__name__)


class KeywordRouter(IntentRouter):
    """Deterministic, zero-latency intent classifier backed by priority_router."""

    async def route(self, message: str, context: Optional[Dict[str, Any]] = None) -> RouteDecision:
        ctx = context or {}
        text = message.strip()
        session_id = ctx.get("session_id", "")

        # Lazy import to avoid circular deps at module load time
        from backend.builder.preference_parser import (
            is_builder_request,
            is_continue_last,
            is_recall_trigger,
            is_update_request,
        )

        # ── Highest specificity first (stateful/session checks) ──────────────
        if is_continue_last(text):
            return RouteDecision("continue", 0.95, {"source": "keyword"})

        if session_id and is_update_request(text, session_id):
            return RouteDecision("update", 0.90, {"source": "keyword", "session_id": session_id})

        # ── Active Builder Confirmation/Rejection Intercept ───────────────────
        user_id = ctx.get("user_id", "local_user")
        bot_id = ctx.get("bot_id", "local_bot")
        from backend.core.context_manager import get_agent_context
        pco = get_agent_context(user_id, bot_id)
        if pco.get("builder_preferences"):
            t_lower = text.lower()
            CONFIRM_WORDS = {"yes", "ok", "okay", "confirm", "go", "start", "done", "proceed"}
            idx_words = t_lower.split()
            if any(w in idx_words for w in CONFIRM_WORDS) or any(w in t_lower for w in ["use this", "build it", "go ahead", "looks good"]):
                return RouteDecision("builder", 0.95, {"source": "keyword", "reason": "active_builder_confirmation"})
            REJECT_WORDS = {"no", "change", "edit", "wait", "actually", "modify", "different"}
            if any(w in idx_words for w in REJECT_WORDS) or "not that" in t_lower:
                return RouteDecision("builder", 0.95, {"source": "keyword", "reason": "active_builder_rejection"})

        # ── Recall trigger ─────────────────────────────────────────────────────
        if is_recall_trigger(text):
            return RouteDecision("recall", 0.85, {"source": "keyword"})

        # ── Autonomous mode detection ──────────────────────────────────────────
        lower = text.lower()
        if any(kw in lower for kw in ("do this task", "automate", "loop")):
            return RouteDecision("autonomous", 0.80, {"source": "keyword"})

        # ── File Analysis Intent ───────────────────────────────────────────────
        file_ids = ctx.get("file_ids", "")
        if file_ids:
            return RouteDecision("file", 0.95, {"source": "keyword", "file_ids": file_ids})

        # ── SINGLE SOURCE OF TRUTH: delegate to priority_router ───────────────
        intent, confidence = detect_intent_with_confidence(text)

        # Map priority_router intents to RouteDecision intents
        if intent == "news":
            return RouteDecision("news", confidence, {"source": "priority_router"})
        if intent == "finance":
            return RouteDecision("tool", confidence, {"source": "priority_router", "tool": "finance"})
        if intent == "weather":
            return RouteDecision("tool", confidence, {"source": "priority_router", "tool": "weather"})
        if intent == "search":
            return RouteDecision("tool", confidence, {"source": "priority_router", "tool": "search"})
        if intent == "builder":
            # Only route to builder if preference_parser also agrees (prevents false positives)
            if is_builder_request(text):
                return RouteDecision("builder", confidence, {"source": "priority_router"})
        if intent == "coding":
            return RouteDecision("chat", 0.85, {"source": "priority_router", "reason": "direct_code"})
        if intent == "autonomous":
            return RouteDecision("autonomous", confidence, {"source": "priority_router"})
        if intent == "debate":
            return RouteDecision("debate", confidence, {"source": "priority_router"})
        if intent == "research":
            return RouteDecision("research", confidence, {"source": "priority_router"})

        # ── Default: low-confidence chat (signals LLM fallback needed) ────────
        return RouteDecision("chat", 0.50, {"source": "keyword"})
