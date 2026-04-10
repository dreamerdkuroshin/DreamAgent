"""
backend/core/semantic_cache.py

Semantic cache with embedding similarity matching and casual rewriting.
- Embeds incoming queries
- Finds similar cached responses (cosine similarity > threshold)
- Rewrites the cached answer in a fresh, natural way (70% chance)
- Falls back to None if no match → normal LLM flow
"""
import logging
import random
import time
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory cache: list of {"query": str, "answer": str, "embedding": list[float], "ts": float}
_CACHE: list = []
MAX_CACHE = 200
SIMILARITY_THRESHOLD = 0.88  # Cosine similarity to consider a "hit"


def _embed(text: str) -> Optional[list]:
    """Generate embedding using SentenceTransformers (already in deps)."""
    try:
        from sentence_transformers import SentenceTransformer
        # Use the same lightweight model the memory manager uses
        model = SentenceTransformer("all-MiniLM-L6-v2")
        vec = model.encode(text, convert_to_numpy=True).tolist()
        return vec
    except Exception as e:
        logger.warning(f"[SemanticCache] Embed failed: {e}")
        return None


def _cosine_similarity(a: list, b: list) -> float:
    """Pure Python cosine similarity — avoids numpy import pain."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(y * y for y in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def find_similar(query: str) -> Optional[dict]:
    """Return the best cache hit (dict with 'answer', 'query') or None."""
    if not _CACHE:
        return None
    q_emb = _embed(query)
    if q_emb is None:
        return None
    best = None
    best_score = 0.0
    for item in _CACHE:
        score = _cosine_similarity(q_emb, item["embedding"])
        if score > best_score:
            best_score = score
            best = item
    if best and best_score >= SIMILARITY_THRESHOLD:
        logger.info(f"[SemanticCache] HIT — score={best_score:.3f} for: {query[:60]}")
        return best
    logger.debug(f"[SemanticCache] MISS — best score={best_score:.3f}")
    return None


def store(query: str, answer: str):
    """Embed the query and store query+answer in the cache."""
    global _CACHE
    emb = _embed(query)
    if emb is None:
        return
    if len(_CACHE) >= MAX_CACHE:
        # FIFO eviction
        _CACHE = _CACHE[-(MAX_CACHE - 1):]
    _CACHE.append({
        "query": query,
        "answer": answer,
        "embedding": emb,
        "ts": time.time()
    })
    logger.debug(f"[SemanticCache] Stored: {query[:50]} (cache size={len(_CACHE)})")


async def rewrite_or_return(cached_answer: str, user_input: str, provider: str = "auto", model: str = "") -> str:
    """
    70% chance: Rewrite the cached answer with a small fast model.
    30% chance: Return the cached answer verbatim (still fast).
    """
    if random.random() > 0.7:
        logger.info("[SemanticCache] Returning verbatim cached answer (30% path)")
        return cached_answer

    from backend.core.persona_engine import get_persona_prompt
    persona = get_persona_prompt(user_input, is_autonomous=False)

    rewrite_prompt = (
        f"{persona}\n\n"
        "Rewrite the answer below in a natural, fresh way.\n"
        "Keep the exact same meaning but change the wording slightly.\n"
        "Make it feel spontaneous and human, NOT like a rephrased copy.\n\n"
        f"User asked: {user_input}\n"
        f"Original answer: {cached_answer}\n\n"
        "Rewritten answer (respond ONLY with the rewritten text, nothing else):"
    )

    try:
        from backend.llm.universal_provider import UniversalProvider
        # Use a fast small model for rewriting — NOT the main reasoning model
        llm = UniversalProvider(provider=provider, model=model or "")
        result = await llm.complete(rewrite_prompt)
        if result and not result.startswith("❌"):
            logger.info("[SemanticCache] Rewrote cached answer successfully")
            return result.strip()
    except Exception as e:
        logger.warning(f"[SemanticCache] Rewrite failed: {e}")

    return cached_answer
