"""
backend/safety.py (Hardened)

Fixes:
  - Case-insensitive + Unicode-normalized blocking
  - Dragonfly-backed rate limiting with in-memory fallback
  - Expanded blocklist with regex
"""
import re
import unicodedata
from time import time
from typing import Dict

# ── Rate Limiter (Dragonfly / Redis-protocol compatible) ──────────────────────
import os as _os
try:
    import redis as _redis
    _dragonfly_url = _os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    _r = _redis.from_url(_dragonfly_url, socket_connect_timeout=1, decode_responses=True)
    _r.ping()
    _REDIS = _r
except Exception:
    _REDIS = None

_MEMORY_RATE: Dict[str, float] = {}
RATE_LIMIT_SECONDS = 2  # 1 request per 2 seconds per user


def check_rate(user_id: str) -> bool:
    """True = request allowed, False = rate limited."""
    key = f"rate:{user_id}"
    now = time()
    if _REDIS:
        try:
            last = _REDIS.get(key)
            if last and (now - float(last)) < RATE_LIMIT_SECONDS:
                return False
            _REDIS.setex(key, 60, str(now))
            return True
        except Exception:
            pass
    # In-memory fallback
    if user_id in _MEMORY_RATE and (now - _MEMORY_RATE[user_id]) < RATE_LIMIT_SECONDS:
        return False
    _MEMORY_RATE[user_id] = now
    return True


# ── Content Safety ────────────────────────────────────────────────────────────
BLOCKED_PATTERNS = [
    r"\bhack(ing|er)?\b",
    r"\bexploit\b",
    r"drop\s+table",
    r"rm\s+-[rf]",
    r"\bsudo\b",
    r"(';|\";\s*--|--\s*$)",  # SQL injection patterns
    r"\bdelete\s+from\b",
    r"\btruncate\s+table\b",
    r"\bshutdown\b",
    r"<script\b",
]

def _normalize(text: str) -> str:
    """Normalize unicode + collapse whitespace to prevent bypass tricks."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower()

def is_safe(text: str) -> bool:
    """Return True if content passes safety checks."""
    if not text:
        return True
    normalized = _normalize(text)
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return False
    return True
