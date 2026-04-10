"""
backend/core/dragonfly_manager.py

Self-healing Dragonfly/Redis connection manager.

Features:
  ∙ Tries to connect at startup
  ∙ Background coroutine retries every RETRY_INTERVAL seconds
  ∙ Flap protection: won't re-announce the same state twice
  ∙ Migration: local_cache → Dragonfly when connection is restored
  ∙ Zero-restart recovery — no uvicorn restart required
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Tuning ───────────────────────────────────────────────────────────────────
RETRY_INTERVAL     = 5      # seconds between reconnect attempts
MIN_SWITCH_INTERVAL = 10    # cooldown to prevent flapping (seconds)
CONNECT_TIMEOUT    = 2      # seconds for ping to respond
FILE_TTL           = 3600   # seconds TTL for uploaded-file cache entries


class DragonflyManager:
    """
    Single source of truth for the Dragonfly connection.

    Components that previously imported `redis_conn` directly should instead
    call `dragonfly.get_client()` so they transparently get the live client
    (or None when unavailable).
    """

    def __init__(self) -> None:
        self._client: Optional[object] = None   # sync redis.Redis instance
        self.mode: str = "fallback"              # "full" | "fallback"
        self._last_switch: float = 0.0
        self._monitor_task: Optional[asyncio.Task] = None

        # In-process fallback stores — used when Dragonfly is down
        self.local_cache: dict  = {}             # key → (json_str, expires_at)
        self.local_queue: list  = []             # simple FIFO list

    # ── Connection ────────────────────────────────────────────────────────────

    def _try_connect_sync(self) -> Optional[object]:
        """Synchronous connect — used during module-load fallback."""
        try:
            import redis as _redis
            url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            client = _redis.from_url(
                url,
                socket_connect_timeout=CONNECT_TIMEOUT,
                decode_responses=True,
            )
            client.ping()
            return client
        except Exception:
            return None

    async def _try_connect_async(self) -> Optional[object]:
        """Async-friendly wrapper — runs the sync connect in a thread."""
        return await asyncio.to_thread(self._try_connect_sync)

    async def connect(self) -> bool:
        """
        Attempt a connection.  Updates mode and migrates local data on upgrade.
        Returns True if connected, False otherwise.
        """
        now = time.monotonic()
        # Flap guard — don't thrash the log if we keep failing
        suppress_log = (now - self._last_switch) < MIN_SWITCH_INTERVAL

        client = await self._try_connect_async()

        if client:
            old_mode = self.mode
            self._client = client
            self.mode = "full"
            self._last_switch = now
            if not suppress_log or old_mode != "full":
                logger.info("✅ Dragonfly connected — switching to FULL mode")
            if old_mode == "fallback":
                await self._migrate_to_dragonfly()
            return True
        else:
            old_mode = self.mode
            self._client = None
            self.mode = "fallback"
            if not suppress_log or old_mode != "fallback":
                logger.warning("⚠️  Dragonfly unavailable — running in FALLBACK mode")
            return False

    # ── Migration ─────────────────────────────────────────────────────────────

    async def _migrate_to_dragonfly(self) -> None:
        """
        Flush in-process cache → Dragonfly when connection is restored.
        Expired entries are dropped; valid entries are replicated with their
        remaining TTL.
        """
        if not self._client or not self.local_cache:
            return

        migrated = 0
        now = time.time()
        expired_keys = []

        for key, (json_str, expires_at) in list(self.local_cache.items()):
            remaining_ttl = int(expires_at - now)
            if remaining_ttl <= 0:
                expired_keys.append(key)
                continue
            try:
                self._client.setex(key, remaining_ttl, json_str)
                migrated += 1
            except Exception as exc:
                logger.warning("[DragonflyMgr] Migration write failed for %s: %s", key, exc)

        for key in expired_keys:
            self.local_cache.pop(key, None)

        self.local_cache.clear()
        logger.info(
            "[DragonflyMgr] Migrated %d entries from local cache → Dragonfly "
            "(%d expired/dropped).",
            migrated,
            len(expired_keys),
        )

    # ── Background Monitor ────────────────────────────────────────────────────

    async def _monitor_loop(self) -> None:
        """Runs forever — attempts reconnect when in fallback mode."""
        while True:
            await asyncio.sleep(RETRY_INTERVAL)
            if self.mode == "fallback":
                await self.connect()
            else:
                # Health-check existing connection
                try:
                    await asyncio.to_thread(self._client.ping)
                except Exception:
                    logger.warning("[DragonflyMgr] Lost Dragonfly connection — entering fallback.")
                    self._client = None
                    self.mode = "fallback"
                    self._last_switch = time.monotonic()

    def start_monitor(self) -> None:
        """Spawn the background monitor task (call from lifespan startup)."""
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(
                self._monitor_loop(), name="dragonfly-monitor"
            )
            logger.info("[DragonflyMgr] Background health monitor started.")

    # ── Public API ────────────────────────────────────────────────────────────

    def get_client(self) -> Optional[object]:
        """Return the live sync redis.Redis client, or None."""
        return self._client

    def is_connected(self) -> bool:
        return self.mode == "full" and self._client is not None

    # ── Status snapshot (for /healthz) ───────────────────────────────────────

    def status(self) -> dict:
        return {
            "mode":       self.mode,
            "dragonfly":  "connected" if self.is_connected() else "disconnected",
            "local_cache_entries": len(self.local_cache),
            "local_queue_items":   len(self.local_queue),
        }


# ─── Module-level singleton ───────────────────────────────────────────────────
dragonfly = DragonflyManager()
