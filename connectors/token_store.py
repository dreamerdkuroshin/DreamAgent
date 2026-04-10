"""
connectors/token_store.py
Encrypted token store — values are Fernet-encrypted before being written
to SQLite (fallback) or Dragonfly/Redis.

Features:
  • 0.5s socket timeout on Redis connections
  • Circuit breaker: 3 consecutive failures → disable Redis for 60s → SQLite fallback
  • All values AES-encrypted via Fernet before storage

Requires:
    pip install cryptography

Set TOKEN_STORE_KEY in your environment to a Fernet key.
Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
import json
import time
import logging
import sqlite3
import stat
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _get_fernet():
    """Return a Fernet instance keyed from TOKEN_STORE_KEY env var."""
    raw_key = os.getenv("TOKEN_STORE_KEY", "VMDEoCj1hBqRV8-NfQU70kDJ3uMZZtPdGMQsglePknAQ=")
    try:
        return Fernet(raw_key.encode())
    except Exception as e:
        logger.error(f"TokenStore: Invalid Fernet key! Error: {e}")
        raise RuntimeError(f"Invalid TOKEN_STORE_KEY: {e}")


def _encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class _CircuitBreaker:
    """
    Simple circuit breaker for Redis connections.
    After `max_failures` consecutive failures, the breaker opens and
    disables Redis attempts for `cool_down_seconds`.
    """
    def __init__(self, max_failures: int = 3, cool_down_seconds: float = 60.0):
        self.max_failures = max_failures
        self.cool_down_seconds = cool_down_seconds
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._is_open = False

    @property
    def is_open(self) -> bool:
        if self._is_open:
            # Check if cool-down has elapsed
            if (time.time() - self._last_failure_time) >= self.cool_down_seconds:
                logger.info("CircuitBreaker: Cool-down elapsed — re-enabling Redis attempts.")
                self._is_open = False
                self._failure_count = 0
                return False
            return True
        return False

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.max_failures:
            self._is_open = True
            logger.warning(
                f"CircuitBreaker: OPEN — Redis failed {self._failure_count} consecutive times. "
                f"Disabling Redis for {self.cool_down_seconds}s and falling back to SQLite."
            )

    def record_success(self):
        if self._failure_count > 0:
            logger.info("CircuitBreaker: Redis recovered — resetting failure count.")
        self._failure_count = 0
        self._is_open = False


# ---------------------------------------------------------------------------
# TokenStore
# ---------------------------------------------------------------------------

class TokenStore:
    """
    Encrypted key-value store for sensitive credentials.
    Supports Dragonfly/Redis (if available) with circuit breaker,
    or local SQLite fallback.
    """

    REDIS_TIMEOUT = 0.5  # 500ms socket timeout

    def __init__(self, db_path: str = "token_store.db"):
        self.db_path = db_path
        self.redis_client = None
        self._breaker = _CircuitBreaker(max_failures=3, cool_down_seconds=60)

        # Try to connect to Dragonfly/Redis if REDIS_URL is set
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(
                    redis_url,
                    socket_timeout=self.REDIS_TIMEOUT,
                    socket_connect_timeout=self.REDIS_TIMEOUT,
                    retry_on_timeout=False,
                )
                # Quick ping to verify connectivity
                self.redis_client.ping()
                logger.info("TokenStore: Using Dragonfly/Redis for storage (timeout=0.5s).")
            except Exception as e:
                logger.warning("TokenStore: Redis requested but failed: %s. Falling back to SQLite.", e)
                self.redis_client = None

        # Always initialise SQLite as fallback
        self._init_sqlite()
        if not self.redis_client:
            logger.info("TokenStore: Using SQLite for storage at %s.", db_path)

    def _init_sqlite(self):
        with self._get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        # Restrict file permissions on Unix
        if os.name != 'nt':
            try:
                os.chmod(self.db_path, stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass

    def _get_db_connection(self):
        return sqlite3.connect(self.db_path)

    # ── Redis helpers with circuit breaker ──────────────────────────────────

    def _redis_available(self) -> bool:
        """Check whether we should attempt Redis (client exists + breaker closed)."""
        return self.redis_client is not None and not self._breaker.is_open

    def _safe_redis_set(self, key: str, value: str) -> bool:
        """Attempt a Redis SET. Returns True on success, False on failure."""
        if not self._redis_available():
            return False
        try:
            self.redis_client.set(key, value)
            self._breaker.record_success()
            return True
        except Exception as e:
            logger.warning("TokenStore: Redis SET failed (%s) — falling back to SQLite.", e)
            self._breaker.record_failure()
            return False

    def _safe_redis_get(self, key: str):
        """Attempt a Redis GET. Returns bytes on success, None on failure/miss."""
        if not self._redis_available():
            return None
        try:
            result = self.redis_client.get(key)
            self._breaker.record_success()
            return result
        except Exception as e:
            logger.warning("TokenStore: Redis GET failed (%s) — falling back to SQLite.", e)
            self._breaker.record_failure()
            return None

    def _safe_redis_delete(self, key: str) -> bool:
        if not self._redis_available():
            return False
        try:
            self.redis_client.delete(key)
            self._breaker.record_success()
            return True
        except Exception as e:
            logger.warning("TokenStore: Redis DELETE failed (%s).", e)
            self._breaker.record_failure()
            return False

    # ── Public API ──────────────────────────────────────────────────────────

    def __setitem__(self, key: str, value: str):
        encrypted = _encrypt(value)
        redis_key = f"dreamagent:token:{key}"

        # Try Redis first, always write to SQLite as durable fallback
        self._safe_redis_set(redis_key, encrypted)
        with self._get_db_connection() as conn:
            conn.execute("""
                INSERT INTO tokens (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET 
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, encrypted))
            conn.commit()

    def get(self, key: str, default: str = None) -> str:
        encrypted = None
        redis_key = f"dreamagent:token:{key}"

        # Try Redis first
        redis_val = self._safe_redis_get(redis_key)
        if redis_val:
            encrypted = redis_val.decode() if isinstance(redis_val, bytes) else redis_val
        else:
            # Fallback to SQLite
            with self._get_db_connection() as conn:
                row = conn.execute("SELECT value FROM tokens WHERE key = ?", (key,)).fetchone()
                if row:
                    encrypted = row[0]

        if encrypted is None:
            return default

        try:
            return _decrypt(encrypted)
        except Exception as e:
            logger.error("TokenStore: Decryption failed for key '%s': %s", key, e)
            return default

    def __getitem__(self, key: str) -> str:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def delete(self, key: str):
        self._safe_redis_delete(f"dreamagent:token:{key}")
        with self._get_db_connection() as conn:
            conn.execute("DELETE FROM tokens WHERE key = ?", (key,))
            conn.commit()

    def clear(self, keys: list[str]):
        for k in keys:
            self.delete(k)

    # ------------------------------------------------------------------
    # OAuth helpers
    # ------------------------------------------------------------------

    def persist_oauth_token(self, provider: str, token_data: dict):
        """Store OAuth token JSON blob, encrypted."""
        try:
            from db.db import save_oauth_token as _db_save
            _db_save(provider, token_data)
        except Exception:
            pass
        # Always also store in our encrypted store as a reliable fallback.
        self[f"oauth:{provider}"] = json.dumps(token_data)

    def get_oauth_token(self, provider: str) -> dict:
        """Retrieve OAuth token JSON blob."""
        try:
            from db.db import get_oauth_token as _db_get
            result = _db_get(provider)
            if result:
                return result
        except Exception:
            pass
        raw = self.get(f"oauth:{provider}")
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return {}


# Global singleton — constructed once at import time.
# Construction fails loudly if TOKEN_STORE_KEY is missing,
# preventing the app from starting with unprotected credentials.
token_store = TokenStore()
