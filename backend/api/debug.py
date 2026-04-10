"""
backend/api/debug.py

Memory debug endpoints to quickly expose vector and DB states.
"""
from fastapi import APIRouter
from backend.core.database import SessionLocal
from backend.core.models import Memory

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])

@router.get("/memory")
def debug_memory(user_id: str = "local_user", bot_id: str = "local_bot"):
    """
    Returns a top-level snapshot of the priority and core memory system for debugging.
    """
    try:
        with SessionLocal() as db:
            core_memories = db.query(Memory).filter(
                Memory.scope == "core",
                Memory.bot_id == bot_id,
                Memory.platform_user_id == user_id
            ).order_by(Memory.importance.desc()).limit(20).all()
            
            top_ranked = db.query(Memory).filter(
                Memory.bot_id == bot_id,
                Memory.platform_user_id == user_id
            ).order_by(Memory.importance.desc(), Memory.access_count.desc()).limit(20).all()
            
            return {
                "success": True,
                "core_memories": [
                    {
                        "category": m.category,
                        "content": m.content,
                        "importance": m.importance,
                        "access_count": m.access_count,
                        "last_accessed": m.last_accessed
                    } for m in core_memories
                ],
                "top_memories": [
                    {
                        "scope": m.scope,
                        "category": m.category,
                        "content": m.content,
                        "importance": m.importance,
                        "access_count": m.access_count,
                        "last_accessed": m.last_accessed
                    } for m in top_ranked
                ]
            }
    except Exception as e:
        return {"success": False, "error": str(e)}
