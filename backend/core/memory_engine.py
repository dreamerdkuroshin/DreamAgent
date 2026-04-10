"""
backend/core/memory_engine.py

Unified 3-Layer Memory Gateway for DreamAgent.

Layer 1 — Session (Dragonfly/Redis):
    Last N conversation turns, TTL 30min per user+bot session.
    LOUD failure if Dragonfly is down — no silent fallback.

Layer 2a — Core Identity (SQLite):
    Facts with scope="core" (name, preferences, goals).
    Always loaded — these are the agent's permanent beliefs.

Layer 2b — Semantic Long-Term (ChromaDB → SQLite fallback):
    Ranked semantic recall via vector similarity.
    ChromaDB is primary; SQLite keyword search is explicit fallback.

Layer 3 — Builder Preferences (AgentContext):
    Structured builder/persona prefs from context_manager.
    Unchanged from previous architecture.
"""
import logging
from typing import Dict, Any, List

from backend.core.database import SessionLocal
from backend.memory.short_term import get_recent_messages
from backend.memory.memory_service import search_memory, store_memory
from backend.core.models import Memory
from backend.memory.memory_extractor import extract_memory
from backend.memory import redis_memory
from backend.memory.identity_store import identity_store
from backend.memory.context_optimizer import context_optimizer

logger = logging.getLogger(__name__)


class MemoryEngine:
    """Unified Memory fetching, saving, and processing engine."""

    # ─── Context Assembly ─────────────────────────────────────────────────────

    @staticmethod
    async def get_context(
        user_id: str,
        bot_id: str,
        conversation_id: int = None,
        user_input: str = ""
    ) -> Dict[str, Any]:
        """
        Retrieves unified context across all 3 memory layers.

        Returns:
            {
                "session":      List[str]  — Layer 1: Dragonfly session turns
                "core_memory":  List[str]  — Layer 2a: Identity facts (scope=core)
                "long_term":    List[str]  — Layer 2b: Semantic recall
                "preferences":  dict       — Layer 3: Builder preferences
            }
        """
        context: Dict[str, Any] = {
            "session":     [],
            "core_memory": [],
            "long_term":   [],
            "preferences": {}
        }

        # ── Layer 1: Short-Term Session (Dragonfly) ────────────────────────
        # redis_memory already logs loud errors if Dragonfly is down.
        try:
            session_turns = redis_memory.get_recent_turns(user_id, bot_id, limit=10)
            context["session"] = [
                f"{t['role'].capitalize()}: {t['content']}"
                for t in session_turns
            ]
        except Exception as e:
            logger.error(
                "[MemoryEngine] Session layer (Dragonfly) failed unexpectedly: %s", e
            )
            context["session"] = []

        # ── Layers 2a + 2b + 3: SQLite / ChromaDB / AgentContext ──────────
        try:
            with SessionLocal() as db:

                # Layer 2a: Core / Identity Memory (Dragonfly + SQLite, scoped)
                try:
                    identity_profile = identity_store.get_profile(user_id, bot_id)
                    core_facts = []
                    
                    if identity_profile:
                        for k, v in identity_profile.items():
                            core_facts.append(f"{k.capitalize()}: {v}")
                            
                    core_memories = db.query(Memory).filter(
                        Memory.scope == "core",
                        Memory.bot_id == bot_id,
                        Memory.platform_user_id == user_id
                    ).limit(15).all()
                    
                    for m in core_memories:
                        core_facts.append(m.content)
                        
                    context["core_memory"] = core_facts
                except Exception as e:
                    logger.error(
                        "[MemoryEngine] Core identity layer failed: %s", e
                    )

                # Layer 2b: Semantic Long-Term (ChromaDB primary, SQLite fallback)
                if user_input:
                    try:
                        semantic = search_memory(
                            db, user_input,
                            limit=5,
                            bot_id=bot_id,
                            platform_user_id=user_id
                        )
                        context["long_term"] = semantic
                    except Exception as e:
                        logger.error(
                            "[MemoryEngine] Semantic layer (vector search) failed: %s", e
                        )

                # Layer 3: Builder Preferences (AgentContext)
                try:
                    from backend.core.context_manager import get_agent_context
                    pco = get_agent_context(user_id, bot_id)
                    if pco and pco.get("builder_preferences"):
                        context["preferences"] = pco.get("builder_preferences")
                except Exception as e:
                    logger.error(
                        "[MemoryEngine] Builder preferences layer (AgentContext) failed: %s", e
                    )

        except Exception as e:
            logger.error(
                "[MemoryEngine] Database session failed — layers 2a/2b/3 unavailable: %s", e
            )

        optimized = await context_optimizer.optimize(context, user_id=user_id, bot_id=bot_id)
        return optimized

    # ─── Storage ──────────────────────────────────────────────────────────────

    @staticmethod
    async def process_and_store(
        message: str,
        user_id: str,
        bot_id: str,
        conversation_id: int = None,
        role: str = "assistant"
    ) -> None:
        """
        Writes a message to both memory layers:
          1. Dragonfly short-term (always attempted)
          2. SQLite long-term (if LLM extractor deems it important)

        Each layer's failure is logged independently — one layer failing
        does NOT prevent the other from being written.
        """
        # Layer 1 write: always store in session (Dragonfly)
        # redis_memory.store_turn already logs loudly on failure.
        redis_memory.store_turn(user_id, bot_id, role, message)

        # Layer 2 write: conditional LLM extraction → SQLite
        try:
            extraction = await extract_memory(message)
        except Exception as e:
            logger.error(
                "[MemoryEngine] Memory extractor crashed for user=%s: %s", user_id, e
            )
            return

        if extraction.store:
            try:
                # Intercept identity-specific fields to store in IdentityStore + SQLite
                if extraction.category in ["identity", "style", "goal_short", "goal_long", "preferences", "dislike"]:
                    identity_store.update_field(user_id, bot_id, extraction.category, extraction.content)
                    logger.info("[MemoryEngine] Updated identity field: %s", extraction.category)

                with SessionLocal() as db:
                    logger.info(
                        "[MemoryEngine] Storing long-term fact (category=%s, importance=%.2f): %s",
                        extraction.category, extraction.importance, extraction.content[:80]
                    )
                    store_memory(
                        db=db,
                        text_content=extraction.content,
                        category=extraction.category,
                        importance=extraction.importance,
                        conversation_id=conversation_id,
                        agent_id=None,
                        bot_id=bot_id,
                        platform_user_id=user_id
                    )
            except Exception as e:
                logger.error(
                    "[MemoryEngine] SQLite long-term store failed for user=%s: %s", user_id, e
                )

    # ─── Context Formatter ────────────────────────────────────────────────────

    @staticmethod
    def format_context_for_prompt(context: Dict[str, Any]) -> str:
        """
        Converts the context dict into a clean string block for LLM prompt injection.
        Merge strategy priority:
          1. Session (Dragonfly) — most recent truth, always wins recency on conflicts
          2. Core Identity (SQLite scope=core) — trusted facts
          3. Semantic LT (ChromaDB) — supporting evidence
        """
        parts: List[str] = []

        if context.get("session"):
            history = "\n".join(context["session"])
            parts.append(f"[RECENT CONVERSATION — highest priority]\n{history}")

        if context.get("core_memory"):
            facts = "\n".join(f"  - {m}" for m in context["core_memory"])
            parts.append(f"[CORE IDENTITY — trusted facts]\n{facts}")

        if context.get("long_term"):
            facts = "\n".join(f"  - {m}" for m in context["long_term"])
            parts.append(f"[SUPPORTING CONTEXT — earlier semantic memory]\n{facts}")

        return "\n\n".join(parts)


# Singleton instance
memory_engine = MemoryEngine()
