"""
backend/core/redis_lock.py

Fail-safe distributed locking with ownership validation and auto-renewal support.
Uses SET NX PX to ensure mutual exclusion and avoid deadlocks on crash.
"""
import uuid
import time
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RedisLock:
    def __init__(self, redis_conn, lock_key: str, expiry_ms: int = 30000):
        self.redis = redis_conn
        self.key = lock_key
        self.expiry = expiry_ms
        self.owner_id = str(uuid.uuid4())
        self._renewal_task = None

    async def acquire(self) -> bool:
        """Attempts to acquire the lock with a unique owner ID."""
        if not self.redis:
            return True # No redis, no lock safety (fallback)
            
        # Check for stale heartbeat before acquiring to fast-fail zombie locks
        try:
            hb = self.redis.get(f"{self.key}:heartbeat")
            if hb:
                last_hb = float(hb.decode() if hasattr(hb, 'decode') else hb)
                if time.time() - last_hb > (self.expiry / 1000) + 2:
                    logger.warning(f"[Lock] Fast-failing zombie lock {self.key} due to stale heartbeat.")
                    self.redis.delete(self.key)
        except Exception:
            pass

        # SET key value NX PX expiry
        try:
            success = self.redis.set(self.key, self.owner_id, nx=True, px=self.expiry)
            if success:
                logger.info(f"[Lock] Acquired {self.key} for owner {self.owner_id}")
                self.redis.set(f"{self.key}:heartbeat", time.time(), ex=int(self.expiry/1000)+5)
                # Start background renewal
                self._renewal_task = asyncio.create_task(self._renew_loop())
                return True
        except Exception as e:
            logger.error(f"[Lock] Failed to acquire {self.key}: {e}")
            
        return False

    async def _renew_loop(self):
        """Background loop to renew the lock every 10s if we still own it."""
        try:
            while True:
                await asyncio.sleep(10) # Renew every 10s
                if not await self.renew():
                    logger.warning(f"[Lock] Failed to renew {self.key}. Ownership lost.")
                    break
        except asyncio.CancelledError:
            pass

    async def renew(self) -> bool:
        """Renews the lock ONLY if the current owner ID matches ours."""
        if not self.redis: return True
        
        # Lua script for atomic check-and-set renewal
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("pexpire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        try:
            result = self.redis.eval(script, 1, self.key, self.owner_id, self.expiry)
            if result:
                self.redis.set(f"{self.key}:heartbeat", time.time(), ex=int(self.expiry/1000)+5)
            return bool(result)
        except Exception as e:
            logger.error(f"[Lock] Renewal failed for {self.key}: {e}")
            return False

    async def release(self):
        """Releases the lock IF we still own it."""
        if self._renewal_task:
            self._renewal_task.cancel()
            
        if not self.redis: return
        
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            self.redis.eval(script, 1, self.key, self.owner_id)
            self.redis.delete(f"{self.key}:heartbeat")
            logger.info(f"[Lock] Released {self.key}")
        except Exception as e:
            logger.error(f"[Lock] Failed to release {self.key}: {e}")

    def is_owner(self) -> bool:
        """Synchronous check (expensive if not local) for ownership."""
        if not self.redis: return True
        current = self.redis.get(self.key)
        if hasattr(current, "decode"): current = current.decode()
        return current == self.owner_id
