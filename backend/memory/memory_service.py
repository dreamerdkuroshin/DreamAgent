"""
backend/memory/memory_service.py

Human-Like Recall System Overhaul
Implements semantic similarity, recency decay, frequency reinforcement,
and priority memory ranking.
"""
import logging
import math
from datetime import datetime
from sqlalchemy import select, text
from backend.core.models import Memory
from backend.core.mode import get_current_mode
from backend.core.task_queue import enqueue_task
from backend.core.database import SessionLocal

def _background_embed(memory_id: int, text_content: str):
    try:
        from backend.memory.embedder import get_embedding
        embedding = get_embedding(text_content)
        if embedding:
            db = SessionLocal()
            try:
                m = db.query(Memory).filter(Memory.id == memory_id).first()
                if m:
                    m.embedding = embedding
                    db.commit()
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Background embedding failed: {e}")

logger = logging.getLogger(__name__)
MAX_MEMORY_ROWS = 1000  # Prune when exceeding this

def cosine_similarity(v1, v2):
    if not v1 or not v2: return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    return dot / (n1 * n2) if n1 and n2 else 0.0

def decay(memory):
    """Memory importance decays over time based on last access."""
    now = datetime.utcnow()
    ref_time = memory.last_accessed if hasattr(memory, "last_accessed") and memory.last_accessed else memory.created_at
    age_days = (now - ref_time).total_seconds() / 86400
    memory.importance *= (0.98 ** max(0, age_days))

def reinforce(db, memory):
    """Accessed memories become stronger and have their last access updated."""
    memory.access_count += 1
    # Check if category allows core promotion
    allow_core = memory.category in ["identity", "preference", "fact", "goal", "project", "skill"]
    
    # Auto-promote to core if highly repeatedly accessed, but ONLY if category allows it
    if allow_core and memory.access_count >= 3 and memory.scope != "core":
        memory.scope = "core"
        
    memory.importance = min(0.95, memory.importance + 0.05)
    
    if hasattr(memory, "last_accessed"):
        memory.last_accessed = datetime.utcnow()
        
    db.commit()

def rank_memory(memories, query_embedding, confidence_threshold: float = 0.65):
    ranked = []
    now = datetime.utcnow()
    for m in memories:
        decay(m) 
        
        sim = cosine_similarity(query_embedding, m.embedding) if query_embedding and m.embedding else 0.5
        
        # Summary Weight Penalty
        if m.category == "conversation_summary":
            sim *= 0.70
            
        ref_time = m.last_accessed if hasattr(m, "last_accessed") and m.last_accessed else m.created_at
        recency = 1.0 / ((now - ref_time).total_seconds() + 1)
        
        imp = m.importance or 0.5
        
        # Retrieval Formula Enforcement
        score = (sim * 0.5) + (recency * 0.3) + (imp * 0.2)
        
        mem_conf = getattr(m, "confidence", 1.0) or 1.0
        
        # ✔ Memory Confidence Gate: score > threshold AND confidence > 0.7
        if score >= confidence_threshold and mem_conf >= 0.7:
            ranked.append((score, m))
        
    ranked.sort(reverse=True, key=lambda x: x[0])
    return [m for _, m in ranked]

def store_memory(
    db, text_content: str, category: str = "general", conversation_id: int = None, 
    scope: str = "personal", agent_id: str = None, bot_id: str = None, 
    platform_user_id: str = None, importance: float = 0.5, confidence: float = 1.0
):
    mode = get_current_mode()

    if not mode.get("store_full_text", True):
        text_content = text_content[:100]

    if mode.get("compression", False) and len(text_content) > 500:
        text_content = text_content[:500]

    embedding = None
    from backend.memory.embedder import get_embedding
    # Synchronously get embedding so we can check for conflicts
    try:
        embedding = get_embedding(text_content)
    except Exception as e:
        logger.warning(f"Failed to embed memory synchronously: {e}")

    # Conflict Resolution & Deduplication
    if embedding:
        # Search for extremely similar existing memories
        existing_memories = search_memory(db, text_content, limit=1, top_k_fetch=5, bot_id=bot_id, platform_user_id=platform_user_id, bypass_reinforce=True, return_objects=True)
        if existing_memories:
            top_match = existing_memories[0]
            sim = cosine_similarity(embedding, top_match.embedding) if top_match.embedding else 0.0
            if sim >= 0.90:
                logger.info(f"Conflict resolution: Merging new memory with existing id={top_match.id}")
                top_match.content = text_content # Update to latest
                top_match.importance = max(top_match.importance, importance)
                reinforce(db, top_match)
                return True

    # Priority Memory (Simulation of Core Identity)
    t = text_content.lower()
    if category in ["identity", "preference", "fact"]:
        if "my name is" in t or "i am called" in t:
            scope = "core"
            importance = max(importance, 0.8)
        
    memory = Memory(
        conversation_id=conversation_id,
        agent_id=agent_id,
        bot_id=bot_id,
        platform_user_id=platform_user_id,
        content=text_content,
        category=category,
        scope=scope,
        importance=importance,
        confidence=confidence,
        access_count=1,
        embedding=embedding
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    
    # If synchronous embedding failed but text is long, let it enqueue
    enqueue = not embedding and len(text_content) >= 50
    if enqueue:
        enqueue_task(_background_embed, memory.id, text_content)

    max_rows = mode.get("max_memories", MAX_MEMORY_ROWS)
    count = db.query(Memory).count()
    if count > max_rows:
        oldest = db.query(Memory).order_by(Memory.created_at.asc()).first()
        if oldest: db.delete(oldest)
        db.commit()


def search_memory(db, query: str, limit: int = 5, top_k_fetch: int = 20, bot_id: str = None, platform_user_id: str = None, bypass_reinforce: bool = False, return_objects: bool = False) -> list:
    """Fetches broad semantic matches, ranks them, reinforces, and returns top N."""
    from backend.memory.embedder import get_embedding
    query_embedding = get_embedding(query)
    memories = []
    try:
        import os
        if os.environ.get("ACTIVE_DB_DIALECT") == "postgresql":
            stmt = select(Memory)
            if bot_id: stmt = stmt.where(Memory.bot_id == bot_id)
            if platform_user_id: stmt = stmt.where(Memory.platform_user_id == platform_user_id)
            
            stmt = stmt.order_by(Memory.embedding.l2_distance(query_embedding)).limit(top_k_fetch)
            results = db.execute(stmt)
            memories = [r[0] for r in results]
        else:
            raise ValueError("pgvector not supported on SQLite")
    except Exception as e:
        logger.warning(f"[memory] Vector search using keyword fallback: {e}")
        keywords = [w for w in query.lower().split() if len(w) > 3]
        
        q = db.query(Memory)
        if bot_id: q = q.filter(Memory.bot_id == bot_id)
        if platform_user_id: q = q.filter(Memory.platform_user_id == platform_user_id)
        
        rows = q.all()
        for row in rows:
            if sum(kw in row.content.lower() for kw in keywords) > 0:
                memories.append(row)
                
    if not memories:
        return []
        
    ranked_memories = rank_memory(memories, query_embedding)[:limit]
    
    if not bypass_reinforce:
        for m in ranked_memories:
            reinforce(db, m)
            
    if return_objects:
        return ranked_memories
        
    return [m.content for m in ranked_memories]
