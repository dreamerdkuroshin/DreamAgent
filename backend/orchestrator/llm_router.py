"""
backend/orchestrator/llm_router.py

LLM-based intent classifier with HARD timeout.
Used as a fallback when the keyword router returns low confidence.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from backend.orchestrator.intent_router import IntentRouter, RouteDecision

logger = logging.getLogger(__name__)

# Hard timeout — prevents the orchestrator from freezing under load
# 2.5s gives the LLM enough time to respond without hanging the pipeline
LLM_ROUTER_TIMEOUT = 2.5  # seconds

ROUTER_SYSTEM_PROMPT = """\
You are an intent classifier for a multi-agent AI system.

Classify the user's message into EXACTLY ONE intent and return ONLY valid JSON:
{
  "intent": "<intent>",
  "tool_choice": "<tool_name if intent is tool, else null>",
  "confidence": <0.0-1.0>
}

Available intents:
- "builder"    → user wants to build/create a website, app, or project
- "update"     → user wants to modify/change an existing project
- "continue"   → user wants to resume/continue a previous project
- "recall"     → user wants to recall/remember previous build preferences
- "autonomous" → user wants a complex multi-step automated task
- "tool"       → user wants to use a specific tool (search, file, code)
- "chat"       → general conversation, questions, greetings

Rules:
- If intent is "tool", set "tool_choice" to one of: "search", "file", "code".
- If unsure, use "chat" with lower confidence
- NEVER output anything except the JSON object
"""

_VALID_INTENTS = {"builder", "update", "continue", "recall", "autonomous", "tool", "chat"}


def _extract_json(text: str) -> Optional[Dict]:
    """Try to extract JSON from LLM response even if wrapped in markdown."""
    # Direct parse
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # Code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    # Bare JSON
    match = re.search(r'\{[^{}]*"intent"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return None


class LLMRouter(IntentRouter):
    """LLM-based intent classifier with hard timeout and graceful fallback."""

    def __init__(self, provider: str = "auto", model: str = ""):
        self._provider = provider
        self._model = model

    async def route(self, message: str, context: Optional[Dict[str, Any]] = None) -> RouteDecision:
        try:
            return await asyncio.wait_for(
                self._classify(message, context),
                timeout=LLM_ROUTER_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[LLMRouter] Classification timed out after %.1fs", LLM_ROUTER_TIMEOUT)
            return RouteDecision("chat", 0.40, {"source": "llm", "fallback": "timeout"})
        except Exception as exc:
            logger.warning("[LLMRouter] Classification failed: %s", exc)
            return RouteDecision("chat", 0.40, {"source": "llm", "fallback": str(exc)})

    async def _classify(self, message: str, context: Optional[Dict[str, Any]] = None) -> RouteDecision:
        from backend.llm.universal_provider import UniversalProvider

        llm = UniversalProvider(provider=self._provider, model=self._model)
        prompt = f"Classify this user message:\n\n\"{message}\""

        raw = await llm.complete(
            f"{ROUTER_SYSTEM_PROMPT}\n\n{prompt}"
        )

        parsed = _extract_json(raw)
        if parsed and "intent" in parsed:
            intent = parsed["intent"]
            if intent not in _VALID_INTENTS:
                intent = "chat"
            confidence = min(max(float(parsed.get("confidence", 0.7)), 0.0), 1.0)
            
            metadata = {"source": "llm"}
            if intent == "tool" and "tool_choice" in parsed and parsed["tool_choice"]:
                metadata["tool"] = parsed["tool_choice"]
                
            logger.info("[LLMRouter] Classified: intent=%s confidence=%.2f", intent, confidence)
            return RouteDecision(intent, confidence, metadata)

        logger.warning("[LLMRouter] Failed to parse response: %s", raw[:120])
        return RouteDecision("chat", 0.50, {"source": "llm", "fallback": "parse_error"})
