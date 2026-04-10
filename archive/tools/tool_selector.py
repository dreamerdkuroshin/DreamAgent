"""
tools/tool_selector.py (V4)

Advanced tool selection:
- Dragonfly-persisted per-tool usage history (success, fail, avg_latency, avg_cost)
- Task-type-aware dynamic weights
- ε-greedy exploration (10% chance to try a less-used tool)
"""

import time
import logging
import random
import json
import os
import re
from typing import List, Dict, Any, Tuple

from tools.registry import registry
from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

# Optional Dragonfly (Redis-protocol compatible)
try:
    from redis import Redis
    _redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    _redis.ping()
except Exception:
    _redis = None
    logger.warning("Dragonfly unavailable – tool stats will be in-memory only.")


# ── weights by task type ──────────────────────────────────────────────
WEIGHTS_BY_TASK: Dict[str, Dict[str, float]] = {
    "research": {
        "relevance": 0.6, "success_rate": 0.2, "latency": -0.05, "cost": -0.05, "context_match": 0.1
    },
    "execution": {
        "relevance": 0.3, "success_rate": 0.2, "latency": -0.3, "cost": -0.1, "context_match": 0.1
    },
    "default": {
        "relevance": 0.4, "success_rate": 0.2, "latency": -0.1, "cost": -0.1, "context_match": 0.2
    },
}

EPSILON = 0.1   # exploration probability


class ToolScorer:
    """Tracks per-tool usage history in Dragonfly with rolling averages."""

    def _key(self, name: str) -> str:
        return f"tool_stats:{name}"

    def record(self, tool_name: str, success: bool, latency: float, cost: float = 0.0):
        if not _redis:
            return
        raw   = _redis.get(self._key(tool_name))
        stats: Dict[str, Any] = json.loads(raw) if raw else {"success": 0, "fail": 0, "avg_latency": 0.0, "avg_cost": 0.0}

        if success:
            stats["success"] += 1
        else:
            stats["fail"] += 1

        total = stats["success"] + stats["fail"]
        stats["avg_latency"] = (stats["avg_latency"] * (total - 1) + latency) / total
        stats["avg_cost"]    = (stats["avg_cost"]    * (total - 1) + cost)    / total

        _redis.set(self._key(tool_name), json.dumps(stats))

    def metrics(self, tool_name: str) -> Dict[str, float]:
        defaults = {"success_rate": 0.5, "avg_latency": 1.0, "avg_cost": 0.1, "total_calls": 0}
        if not _redis:
            return defaults
        raw = _redis.get(self._key(tool_name))
        if not raw:
            return defaults
        s = json.loads(raw)
        total = s["success"] + s["fail"]
        return {
            "success_rate": s["success"] / total if total else 0.5,
            "avg_latency":  s["avg_latency"],
            "avg_cost":     s["avg_cost"],
            "total_calls":  total,
        }


class ToolSelector:
    def __init__(self, agent_id: str = "default"):
        self.registry = registry
        self.memory   = MemoryManager(agent_id=agent_id)
        self.scorer   = ToolScorer()

    def select_tools(
        self,
        task_description: str,
        context: str = "",
        task_type: str = "default",
        max_tools: int = 4,
    ) -> List[Tuple[str, float]]:
        """
        V4 scoring with dynamic weights + ε-greedy exploration.

        score = relevance*W_rel + success_rate*W_suc - latency_norm*|W_lat| - cost_norm*|W_cost| + context_match*W_ctx
        """
        weights   = WEIGHTS_BY_TASK.get(task_type, WEIGHTS_BY_TASK["default"])
        all_tools = self.registry.list_tools()
        scored: List[Tuple[str, float]] = []

        for name in all_tools:
            info = self.registry.get_tool(name)
            if not info:
                continue

            m            = self.scorer.metrics(name)
            relevance    = self._relevance(task_description, info)
            ctx_match    = self._relevance(context, info) if context else relevance
            latency_norm = min(1.0, m["avg_latency"] / 5.0)
            cost_norm    = min(1.0, m["avg_cost"]    / 0.5)

            score = (
                relevance           * weights["relevance"]
                + m["success_rate"] * weights["success_rate"]
                + latency_norm      * weights["latency"]   # negative weight
                + cost_norm         * weights["cost"]       # negative weight
                + ctx_match         * weights["context_match"]
            )
            scored.append((name, round(score, 4)))

        # Sort descending
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:max_tools]

        # ε-greedy: occasionally swap one top tool for a less-explored one
        if len(scored) > max_tools and random.random() < EPSILON:
            candidates = scored[max_tools:]       # tools outside the top
            # prefer least-used tools for exploration
            candidates.sort(key=lambda x: self.scorer.metrics(x[0])["total_calls"])
            explore = candidates[0]
            logger.debug("ε-greedy: exploring tool '%s' (score=%.4f)", explore[0], explore[1])
            top[-1] = explore  # replace the lowest-ranked top tool

        return top

    # ------------------------------------------------------------------

    def _relevance(self, text: str, info: Dict[str, Any]) -> float:
        if not text:
            return 0.0
        score      = 0.0
        text_lower = text.lower()
        name_lower = info.get("name", "").lower()
        desc_lower = info.get("description", "").lower()

        if name_lower in text_lower:
            score += 0.5

        kw = self._keywords(desc_lower)
        if kw:
            hits = sum(1 for w in kw if w in text_lower)
            score += 0.5 * min(1.0, hits / max(1, len(kw) // 3))

        return min(1.0, score)

    @staticmethod
    def _keywords(text: str) -> List[str]:
        stop = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        return [w for w in re.findall(r"\b\w+\b", text) if w not in stop and len(w) > 2]