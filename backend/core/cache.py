"""
backend/core/cache.py  (v2 — backed by DragonflyManager)

Unified async-safe cache layer.
  ∙ Full mode   → Dragonfly/Redis  (setex / get / delete)
  ∙ Fallback    → DragonflyManager.local_cache dict (in-process, migrates on reconnect)
  ∙ Same API either way — callers never need to know which backend is active.
"""
from __future__ import annotations

import json
import time
import logging
from typing import Any, Optional

from backend.core.dragonfly_manager import dragonfly

logger = logging.getLogger(__name__)


def cache_get(key: str) -> Optional[Any]:
    """Return cached value (deserialized) or None."""
    client = dragonfly.get_client()

    if client:
        try:
            raw = client.get(key)
            if raw is not None:
                logger.debug("[Cache] HIT  key=%s (dragonfly)", key)
                return json.loads(raw)
        except Exception as exc:
            logger.warning("[Cache] Dragonfly get error (%s), falling back: %s", key, exc)
            # Fall through to local cache

    # Local fallback
    entry = dragonfly.local_cache.get(key)
    if entry:
        value_str, expires_at = entry
        if expires_at > time.time():
            logger.debug("[Cache] HIT  key=%s (local)", key)
            return json.loads(value_str)
        dragonfly.local_cache.pop(key, None)
    return None


def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Store value (serialized) with a TTL in seconds."""
    raw = json.dumps(value)
    client = dragonfly.get_client()

    if client:
        try:
            client.setex(key, ttl, raw)
            logger.debug("[Cache] SET  key=%s ttl=%ds (dragonfly)", key, ttl)
            return
        except Exception as exc:
            logger.warning("[Cache] Dragonfly set error (%s), writing to local: %s", key, exc)

    # Local fallback — will be migrated to Dragonfly on reconnect
    dragonfly.local_cache[key] = (raw, time.time() + ttl)
    logger.debug("[Cache] SET  key=%s ttl=%ds (local fallback)", key, ttl)


def cache_delete(key: str) -> None:
    """Invalidate a cache key from both backends."""
    client = dragonfly.get_client()
    if client:
        try:
            client.delete(key)
        except Exception:
            pass
    dragonfly.local_cache.pop(key, None)
