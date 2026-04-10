"""
backend/agents/memory_agent.py

MemoryAgent — Proactive memory extraction and retrieval.
Responsible for ensuring "my name is manthan" gets permanently recorded and retrieved.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from backend.core.database import SessionLocal
from backend.memory.memory_manager import build_context, extract_and_store
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

MEMORY_EXTRACTION_SYSTEM = """You are a Memory Agent. 
Determine if the user's input contains any long-term identity facts, preferences, or important state that should be remembered forever.
If so, extract it into a clean factual string. If not, return no_fact.

EXAMPLES:
"my name is manthan" -> "The user's name is manthan."
"i like python" -> "The user likes the Python programming language."
"how do i write a loop" -> "no_fact"
"build a discord bot" -> "no_fact"

Respond ONLY with the extracted fact or "no_fact".w
"""

class MemoryAgent(BaseAgent):
    """Proactively stores and retrieves context."""

    def __init__(self, llm, tools=None):
        super().__init__(llm, memory=None, tools=tools, role="memory")

    async def get_context(self, user_input: str, conversation_id: Optional[int] = None, bot_id: Optional[str] = None, platform_user_id: Optional[str] = None) -> str:
        """Retrieves formatted context for the Orchestrator."""
        try:
            with SessionLocal() as db:
                ctx_dict = build_context(db, conversation_id, user_input, bot_id=bot_id, platform_user_id=platform_user_id)
                
                parts = []
                if ctx_dict.get("core_memory"):
                    parts.append("[CORE IDENTITY FACTS]\n" + "\n".join(ctx_dict["core_memory"]))
                if ctx_dict.get("long_term"):
                    parts.append("[RELEVANT SEMANTIC MEMORY]\n" + "\n".join(ctx_dict["long_term"]))
                if ctx_dict.get("short_term"):
                    parts.append("[RECENT CONVERSATION]\n" + "\n".join(ctx_dict["short_term"]))
                
                return "\n\n".join(parts)
        except Exception as e:
            logger.error(f"[MemoryAgent] Context retrieval failed: {e}")
            return ""

    async def process_and_store(self, user_input: str, conversation_id: Optional[int] = None, bot_id: Optional[str] = None, platform_user_id: Optional[str] = None):
        """Uses LLM to evaluate if the input contains a core fact, and stores it in the isolated DB."""
        # 1. Ask LLM to extract facts
        prompt = f"User input: {user_input}"
        extracted = await self.think(prompt, system=MEMORY_EXTRACTION_SYSTEM)
        extracted = extracted.strip()

        if extracted.lower() not in ["no_fact", '"no_fact"', "'no_fact'", "none", "n/a"]:
            logger.info(f"[MemoryAgent] Extracted new core fact: {extracted}")
            
            # 2. Store it directly using backend/memory_manager.py's isolated function
            try:
                with SessionLocal() as db:
                    # We pass the extracted fact, bypassing the naive keyword filter by prepending "my name is" magically
                    # Actually, the extract_and_store keyword filter will still block it if it doesn't contain matching words.
                    # Let's write directly to store_memory here so it bypasses the dumb filter.
                    from backend.memory.memory_service import store_memory
                    store_memory(
                        db, 
                        extracted, 
                        category="fact", 
                        conversation_id=conversation_id, 
                        scope="core", 
                        bot_id=bot_id, 
                        platform_user_id=platform_user_id
                    )
            except Exception as e:
                logger.error(f"[MemoryAgent] Force store failed: {e}")
