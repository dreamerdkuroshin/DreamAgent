"""
backend/orchestrator/hybrid_router.py

Production router: keyword fast-path → LLM fallback.
Fast for ~80 % of queries, smart for the rest.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.orchestrator.intent_router import IntentRouter, RouteDecision
from backend.orchestrator.keyword_router import KeywordRouter
from backend.orchestrator.llm_router import LLMRouter

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.80


class HybridRouter(IntentRouter):
    """
    Two-tier intent router:
      1. Keyword check (instant, deterministic)
      2. LLM fallback (300-800 ms, only for ambiguous queries)
    """

    def __init__(self, provider: str = "auto", model: str = ""):
        self.keyword_router = KeywordRouter()
        self.llm_router = LLMRouter(provider=provider, model=model)

    async def route(self, message: str, context: Optional[Dict[str, Any]] = None) -> RouteDecision:
        # Step 0 - Hardware trap for builder mode
        if context and context.get("mode") == "builder":
            if message.lower().strip() in ["exit", "cancel", "stop", "nevermind", "quit"]:
                # The caller should clear the mode, but we indicate a chat fallback
                logger.info("[HybridRouter] User breaking out of builder trap.")
                return RouteDecision("exit_builder", 1.0, {"source": "hybrid"})
            return RouteDecision("builder", 1.0, {"source": "hybrid"})

        # Step 0b — Direct fast-path for builder form JSON submissions
        if message.strip().startswith("Build this website:"):
            logger.info("[HybridRouter] Builder form JSON submission detected.")
            return RouteDecision("builder", 1.0, {"source": "form_submit"})

        # Step 1 — fast keyword pre-check
        kw_result = await self.keyword_router.route(message, context)

        if kw_result.confidence >= CONFIDENCE_THRESHOLD:
            logger.info("[HybridRouter] Keyword hit: %s (%.0f%%)", kw_result.intent, kw_result.confidence * 100)
            return kw_result

        # Step 2 — LLM fallback for ambiguous messages
        logger.info("[HybridRouter] Keyword confidence %.0f%% < threshold, delegating to LLM", kw_result.confidence * 100)
        llm_result = await self.llm_router.route(message, context)

        if llm_result.confidence > 0.75:
            return llm_result

        # Step 3 — LLM also unsure. Use keyword best-guess rather than annoying clarification.
        # Only ask for clarification if keyword router had absolutely zero signal.
        if kw_result.confidence > 0.0:
            logger.info(
                "[HybridRouter] LLM unsure (%.0f%%), falling back to keyword best-guess: %s (%.0f%%)",
                llm_result.confidence * 100, kw_result.intent, kw_result.confidence * 100
            )
            return kw_result

        # Both routers have no signal — default to autonomous chat rather than clarification
        logger.info("[HybridRouter] Both routers uncertain, defaulting to autonomous.")
        return RouteDecision("autonomous", 0.60, {"source": "hybrid", "fallback": "default"})
