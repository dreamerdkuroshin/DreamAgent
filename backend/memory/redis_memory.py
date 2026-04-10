"""
backend/memory/redis_memory.py

Dragonfly-backed short-term session memory for DreamAgent.

Architecture layer: Layer 1 (short-term, session-scoped)
  - Stores conversation turns per user+bot with a 30-minute TTL
  - Uses DragonflyManager (never holds its own Redis reference)
  - LOUD failures: if Dragonfly is down, logs error and returns empty — no silent deque

Key schema:
  mem:{user_id}:{bot_id}:turns  → Redis List of JSON strings, newest at right
  TTL: 1800 seconds (30 min), refreshed on every store
"""
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Maximum turns kept in the session window
SESSION_TURN_LIMIT = 20
SESSION_TTL_SECONDS = 1800  # 30 minutes


def _get_client():
    """Always fetches the live Dragonfly client via the self-healing manager."""
    from backend.core.dragonfly_manager import dragonfly
    return dragonfly.get_client()


def _session_key(user_id: str, bot_id: str) -> str:
    return f"mem:{user_id}:{bot_id}:turns"


def store_turn(user_id: str, bot_id: str, role: str, content: str) -> bool:
    """
    Appends one conversation turn to the session ring buffer in Dragonfly.

    Returns True on success, False on failure.
    Failure is always logged loudly — never swallowed.
    """
    client = _get_client()
    if client is None:
        logger.error(
            "[RedisMemory] Dragonfly unavailable — short-term memory DISABLED. "
            "Turn not stored for user=%s bot=%s", user_id, bot_id
        )
        return False

    key = _session_key(user_id, bot_id)
    entry = json.dumps({"role": role, "content": content})

    try:
        # Push to right (newest), trim to keep only last SESSION_TURN_LIMIT turns
        client.rpush(key, entry)
        client.ltrim(key, -SESSION_TURN_LIMIT, -1)
        client.expire(key, SESSION_TTL_SECONDS)
        return True
    except Exception as exc:
        logger.error(
            "[RedisMemory] Failed to store turn for user=%s bot=%s: %s",
            user_id, bot_id, exc
        )
        return False


def get_recent_turns(user_id: str, bot_id: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    Retrieves the last `limit` conversation turns for the session.

    Returns a list of dicts: [{"role": "user", "content": "..."}, ...]
    Returns [] on ANY failure — failure is always logged loudly.
    """
    client = _get_client()
    if client is None:
        logger.error(
            "[RedisMemory] Dragonfly unavailable — cannot retrieve session history "
            "for user=%s bot=%s. Returning empty context.", user_id, bot_id
        )
        return []

    key = _session_key(user_id, bot_id)

    try:
        # LRANGE with negative indices: -limit means 'last N items'
        raw_entries = client.lrange(key, -limit, -1)
        if not raw_entries:
            return []

        turns = []
        for raw in raw_entries:
            try:
                turn = json.loads(raw)
                if isinstance(turn, dict) and "role" in turn and "content" in turn:
                    turns.append(turn)
            except (json.JSONDecodeError, TypeError) as parse_err:
                logger.warning(
                    "[RedisMemory] Skipped malformed turn entry for user=%s: %s",
                    user_id, parse_err
                )
        return turns

    except Exception as exc:
        logger.error(
            "[RedisMemory] Failed to retrieve turns for user=%s bot=%s: %s",
            user_id, bot_id, exc
        )
        return []


def flush_session(user_id: str, bot_id: str) -> bool:
    """
    Clears the session memory for this user+bot pair.
    Used on explicit user reset or logout.

    Returns True on success, False (logged) on failure.
    """
    client = _get_client()
    if client is None:
        logger.error(
            "[RedisMemory] Dragonfly unavailable — cannot flush session "
            "for user=%s bot=%s.", user_id, bot_id
        )
        return False

    key = _session_key(user_id, bot_id)
    try:
        client.delete(key)
        logger.info("[RedisMemory] Session flushed for user=%s bot=%s", user_id, bot_id)
        return True
    except Exception as exc:
        logger.error(
            "[RedisMemory] Failed to flush session for user=%s bot=%s: %s",
            user_id, bot_id, exc
        )
        return False


def get_all_turns(user_id: str, bot_id: str) -> List[Dict[str, str]]:
    """Retrieves all stored conversation turns for the session."""
    return get_recent_turns(user_id, bot_id, limit=-1)

def replace_turns(user_id: str, bot_id: str, turns: List[Dict[str, str]]) -> bool:
    """Overwrites the session ring buffer entirely with a new list of turns.
    Often used after summarization to compact the history."""
    client = _get_client()
    if client is None:
        logger.error(
            "[RedisMemory] Dragonfly unavailable — cannot replace session turns "
            "for user=%s bot=%s.", user_id, bot_id
        )
        return False
        
    key = _session_key(user_id, bot_id)
    try:
        pipeline = client.pipeline()
        pipeline.delete(key)
        if turns:
            # RPUSH backwards or forwards? RPUSH pushes to end.
            for turn in turns:
                pipeline.rpush(key, json.dumps(turn))
            pipeline.ltrim(key, -SESSION_TURN_LIMIT, -1)
            pipeline.expire(key, SESSION_TTL_SECONDS)
        pipeline.execute()
        return True
    except Exception as exc:
        logger.error(
            "[RedisMemory] Failed to replace turns for user=%s bot=%s: %s",
            user_id, bot_id, exc
        )
        return False

def get_session_as_string(user_id: str, bot_id: str, limit: int = 10) -> str:
    """
    Convenience function — returns session turns as a formatted string
    ready for LLM context injection.

    Returns "" if session is empty or Dragonfly is unavailable.
    """
    turns = get_recent_turns(user_id, bot_id, limit=limit)
    if not turns:
        return ""
    return "\n".join(f"{t['role'].capitalize()}: {t['content']}" for t in turns)
