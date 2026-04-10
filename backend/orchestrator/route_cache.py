"""
backend/orchestrator/route_cache.py

Session-aware routing cache with hybrid scope:
  - Global cache for context-free intents (builder, chat)
  - Session-scoped cache for context-sensitive intents (update, continue, recall)

Cache key includes session/user context to prevent ghost bugs.
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from backend.orchestrator.intent_router import IntentRouter, RouteDecision

logger = logging.getLogger(__name__)

# Intents that are safe to cache globally (independent of user context)
_GLOBAL_SAFE_INTENTS = {"builder", "chat", "tool", "autonomous"}


class CachedRouter(IntentRouter):
    """
    Wraps any IntentRouter with a TTL + LRU cache layer.
    Cache keys incorporate session context to prevent cross-user ghost bugs.
    """

    def __init__(
        self,
        inner: IntentRouter,
        ttl_seconds: int = 300,
        max_size: int = 500,
    ):
        self._inner = inner
        self._ttl = ttl_seconds
        self._max_size = max_size
        # OrderedDict for LRU eviction: key → (RouteDecision, timestamp)
        self._cache: OrderedDict[str, Tuple[RouteDecision, float]] = OrderedDict()

    def _make_key(self, message: str, context: Optional[Dict[str, Any]]) -> str:
        """
        Build a cache key that respects session context.
        Prevents 'continue my last build' from returning stale routes
        for different users/sessions.
        """
        ctx = context or {}
        session_id = ctx.get("session_id", "")
        user_id = ctx.get("user_id", "anon")
        raw = f"{message}:{session_id}:{user_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _evict_expired(self) -> None:
        """Remove entries older than TTL."""
        now = time.time()
        expired = [k for k, (_, ts) in self._cache.items() if now - ts > self._ttl]
        for k in expired:
            del self._cache[k]

    def _evict_lru(self) -> None:
        """Pop oldest entry if cache exceeds max_size."""
        while len(self._cache) >= self._max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug("[RouteCache] LRU evict: %s", evicted_key)

    async def route(self, message: str, context: Optional[Dict[str, Any]] = None) -> RouteDecision:
        self._evict_expired()

        key = self._make_key(message, context)

        # Cache hit
        if key in self._cache:
            decision, ts = self._cache[key]
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            logger.info("[RouteCache] HIT key=%s intent=%s", key[:8], decision.intent)
            return decision

        # Cache miss — delegate to inner router
        decision = await self._inner.route(message, context)

        # Only cache high-confidence decisions
        if decision.confidence >= 0.70:
            self._evict_lru()
            self._cache[key] = (decision, time.time())
            logger.debug("[RouteCache] STORED key=%s intent=%s", key[:8], decision.intent)
        else:
            logger.debug("[RouteCache] SKIP low-confidence (%.2f)", decision.confidence)

        return decision

    def invalidate(self, message: str = None, context: Dict[str, Any] = None) -> None:
        """Manually invalidate a specific entry or clear the entire cache."""
        if message is not None:
            key = self._make_key(message, context)
            self._cache.pop(key, None)
        else:
            self._cache.clear()
            logger.info("[RouteCache] Cache cleared")

    @property
    def size(self) -> int:
        return len(self._cache)
