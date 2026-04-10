"""
backend/memory/memory_manager.py

3-Layer Memory System:
  Layer 1 — Short-term: last N conversation messages
  Layer 2 — Semantic:   important facts filtered by should_store()
  Layer 3 — Persona:    preferences/facts extracted and stored persistently
"""

import logging
from backend.memory.short_term import get_recent_messages
from backend.memory.memory_service import search_memory, store_memory
from backend.core.models import Memory
from backend.core.mode import get_current_mode

logger = logging.getLogger(__name__)

# ── Layer 2: Semantic filter ───────────────────────────────────────────────────
_STORE_KEYWORDS = [
    "my name is", "i am called", "i like", "i love", "i hate", "i prefer",
    "i want", "i need", "remember", "important", "don't forget", "note that",
    "my favorite", "i work", "i live", "i use", "my goal", "my project",
    "i'm building", "i am building",
]

def should_store(text: str) -> bool:
    """Return True if the text contains information worth persisting."""
    t = text.lower()
    return any(kw in t for kw in _STORE_KEYWORDS)


def categorize(text: str) -> str:
    """Categorize memory content for structured retrieval."""
    t = text.lower()
    if any(k in t for k in ["i like", "prefer", "favorite", "love", "hate"]):
        return "preference"
    if any(k in t for k in ["my name is", "i am called", "i work", "i live"]):
        return "fact"
    if any(k in t for k in ["todo", "task", "goal", "project", "building"]):
        return "task"
    return "general"


def extract_and_store(db, text: str, conversation_id: int = None, bot_id: str = None, platform_user_id: str = None) -> bool:
    """
    If text passes the should_store filter, save it to persistent memory.
    Returns True if stored.
    """
    if not should_store(text):
        return False
    try:
        category = categorize(text)
        store_memory(db, text, category=category, conversation_id=conversation_id, bot_id=bot_id, platform_user_id=platform_user_id)
        logger.info(f"[Memory] Stored ({category}): {text[:80]}")
        return True
    except Exception as e:
        logger.warning(f"[Memory] Failed to store: {e}")
        return False


def build_context(db, conversation_id: int, user_input: str, bot_id: str = None, platform_user_id: str = None) -> dict:
    """
    Builds a structured Context Dictionary combining:
    - short_term: Recent messages from the current conversation
    - long_term: Ranked semantic memories via vector search (isolated)
    - core_memory: Identity facts explicitly saved under 'core' scope (isolated)
    """
    context = {
        "short_term": [],
        "long_term": [],
        "core_memory": []
    }

    mode = get_current_mode()

    # ── Layer 2: Long-Term Semantic Memory (Ranked & Isolated) ────────
    try:
        ranked_memories = search_memory(db, user_input, limit=mode.get("top_k", 5), bot_id=bot_id, platform_user_id=platform_user_id)
        context["long_term"] = ranked_memories
    except Exception as e:
        logger.warning(f"[Memory] Semantic ranking failed: {e}")

    # ── Layer 3: Core Memory (Identity / Crucial Facts, Isolated) ────
    try:
        q = db.query(Memory).filter(Memory.scope == "core")
        if bot_id:
            q = q.filter(Memory.bot_id == bot_id)
        if platform_user_id:
            q = q.filter(Memory.platform_user_id == platform_user_id)
            
        core_facts = q.limit(10).all()
        context["core_memory"] = [m.content for m in core_facts]
    except Exception as e:
        logger.warning(f"[Memory] Core memory retrieval failed: {e}")

    # ── Layer 1: Short-Term Conversation History ───────────
    try:
        if conversation_id:
            recent = get_recent_messages(db, conversation_id, limit=mode.get("short_memory", 10))
            if recent:
                context["short_term"] = [f"{m.role}: {m.content}" for m in reversed(recent)]
    except Exception as e:
        logger.warning(f"[Memory] Short-term retrieval failed: {e}")

    return context
