import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, ValidationError

from backend.core.database import SessionLocal
from backend.core.models import AgentContext

logger = logging.getLogger(__name__)

# --- Pydantic Schema Guards ---
class IdentityContext(BaseModel):
    name: str = "DreamAgent"
    role: str = "AI assistant"
    tone: str = "professional"

class UserContext(BaseModel):
    name: str = "Manthan"
    workspace: str = "DreamAgent"

class DirectivesContext(BaseModel):
    mode_detection: bool = True
    no_hallucination: bool = True
    tool_priority: bool = True

class MemoryLogEntry(BaseModel):
    date: str
    event: str

class LastBuildContext(BaseModel):
    session_id: str = ""
    type: str = ""
    design: str = ""
    path: str = ""
    file_count: int = 0

class AgentContextSchema(BaseModel):
    identity: IdentityContext = IdentityContext()
    user: UserContext = UserContext()
    directives: DirectivesContext = DirectivesContext()
    builder_preferences: dict = {}
    last_build: dict = {}
    memory_log: list[MemoryLogEntry] = []
    compressed_summary: str = ""

DEFAULT_CONTEXT = AgentContextSchema().model_dump()


# --- DB Operations ---
def get_agent_context(user_id: str, bot_id: str) -> dict:
    """Load context from database. If not found, create default context."""
    with SessionLocal() as db:
        record = db.query(AgentContext).filter_by(user_id=user_id, bot_id=bot_id).first()
        if record and record.context:
            try:
                # Schema Guard: validate existing DB data
                validated = AgentContextSchema(**record.context)
                return validated.model_dump()
            except ValidationError as e:
                logger.warning(f"[PCO] Invalid DB context for {user_id}/{bot_id}: {e}. Falling back to default.")
                return DEFAULT_CONTEXT.copy()
        
        # Create initial record
        new_record = AgentContext(user_id=user_id, bot_id=bot_id, context=DEFAULT_CONTEXT)
        db.add(new_record)
        db.commit()
        return DEFAULT_CONTEXT.copy()

def delete_agent_context(user_id: str, bot_id: str) -> bool:
    """Wipes the context for the requested user/bot pairing."""
    with SessionLocal() as db:
        record = db.query(AgentContext).filter_by(user_id=user_id, bot_id=bot_id).first()
        if record:
            db.delete(record)
            db.commit()
            return True
        return False

def save_agent_context(user_id: str, bot_id: str, context: dict) -> None:
    """Save the updated context into the DB."""
    # Note: memory pruning to MAX items is handled internally by update_context using compression.

    # 2. Enforcement #2: Schema validation guard
    try:
        validated = AgentContextSchema(**context)
        final_context = validated.model_dump()
    except ValidationError as e:
        logger.error(f"[PCO] Aborting save due to schema validation failure: {e}")
        return

    with SessionLocal() as db:
        record = db.query(AgentContext).filter_by(user_id=user_id, bot_id=bot_id).first()
        if record:
            record.context = final_context
            db.commit()
        else:
            new_record = AgentContext(user_id=user_id, bot_id=bot_id, context=final_context)
            db.add(new_record)
            db.commit()

# --- LLM Integration ---
def build_system_prompt(context: dict) -> str:
    """Injects the JSON context into a System Prompt string."""
    ident = context.get('identity', {})
    usr = context.get('user', {})
    
    core_mem = context.get('core_memory', [])
    core_block = ""
    if core_mem:
        facts = "\n".join([f"- {m}" for m in core_mem])
        core_block = f"\n[SYSTEM INSTRUCTIONS]: You know the following core facts about the user:\n{facts}\nUse these facts proactively when relevant to the conversation.\n"
        
    long_term = context.get('long_term', [])
    long_term_block = ""
    if long_term:
        facts = "\n".join([f"- {m}" for m in long_term])
        long_term_block = f"\n[RELEVANT SEMANTIC MEMORY]:\n{facts}\n"

    # Format recent memory efficiently
    recent_mem = context.get('memory_log', [])
    mem_str = "\n".join([f"- [{m.get('date', '')}] {m.get('event', '')}" for m in recent_mem]) if recent_mem else "None"
    
    comp_sum = context.get('compressed_summary', '')
    comp_block = f"\nLong-Term Context:\n{comp_sum}\n" if comp_sum else ""

    builder_prefs = context.get('builder_preferences', context.get('preferences', {}))
    builder_block = ""
    if builder_prefs:
        builder_block = f"""
CRITICAL BUILDER DIRECTIVE:
You have active Builder Preferences saved:
{json.dumps(builder_prefs, indent=2)}

If the user says "use this", "yes", or "build it", you will NOT answer with text.
You are the DreamAgent Builder. You must execute the build process.
(Note: the backend will intercept this request and build automatically, just agree and let the system handle it.)
"""

    has_memory = bool(core_mem or long_term)
    memory_instruction = (
        "Use the above memory context ONLY if it directly impacts the request.\n"
        "- Do NOT infer or extend memory beyond what is written.\n"
        "- If memory is completely unrelated, ignore it completely.\n"
        "- Do NOT say 'I remember' if no memory was provided."
        if has_memory else
        "No prior memory context is available. Do NOT claim to remember anything."
    )

    return f"""You are {ident.get('name', 'DreamAgent')}, a {ident.get('role', 'helpful AI assistant')}.
Tone: {ident.get('tone', 'professional')}

[USER IDENTITY]
Name: {usr.get('name', 'Unknown')}
Workspace: {usr.get('workspace', 'Unknown')}
{comp_block}
{core_block}
{long_term_block}
{builder_block}

[RECENT SYSTEM MEMORY]
{mem_str}

[INSTRUCTIONS]
{memory_instruction}
- Do NOT hallucinate facts, prices, news, or live data.
- If asked for real-time information, use tools (WebSearch/Browser) or explicitly state you cannot access it.
- Answer concisely unless the user asks for detail.
"""

async def compress_old_memory(old_memories: list) -> str:
    """Uses a cheap LLM to summarize older memories and free up the log array."""
    from backend.llm.universal_provider import UniversalProvider
    
    # We use a cheaper and faster dedicated model for background summarization
    llm = UniversalProvider(provider="gemini", model="gemini-2.5-flash")
    
    mem_lines = "\n".join([f"- [{m.get('date', '')}] {m.get('event', '')}" for m in old_memories])
    prompt = f"""Summarize this memory into key long-term facts:
- identity
- preferences
- goals
- important context

Memory Logs:
{mem_lines}

Remove noise. Keep it concise and useful.
"""
    try:
        summary = await llm.get_chat_completion(prompt)
        return summary.strip()
    except Exception as e:
        logger.error(f"[PCO] Failed to compress memory: {e}")
        return ""


async def update_context(provider_llm_instance, context: dict, message: str) -> dict:
    """Updates context via an LLM call based on the user's latest message."""
    import re
    
    prompt = f"""You are updating a persistent AI memory.

Current Context JSON:
{json.dumps(context, indent=2)}

New Message:
{message}

Rules:
1. Update existing fields (like tone, user name) only if requested.
2. DO NOT add casual chat or trivial details.
3. If an important event occurred, APPEND it to the "memory_log" array inside context JSON. Use today's date '{datetime.utcnow().strftime("%Y-%m-%d")}'.
4. Return ONLY the fully updated JSON object. No explanation, no markdown blocks.
5. If the user specifies website builder preferences (e.g., "modern + sell products + full app"), EXTRACT them and update the "builder_preferences" dict (e.g., {{ "design": "modern", "backend": true, "type": "ecommerce" }}).
"""

    try:
        # Assuming provider_llm_instance has a generic .generate or similar.
        # Fallback to .generate([...]) which is common in UniversalProvider.
        if hasattr(provider_llm_instance, "generate"):
            updated_text = provider_llm_instance.generate([{"role": "user", "content": prompt}])
        elif hasattr(provider_llm_instance, "get_chat_completion"):
            updated_text = await provider_llm_instance.get_chat_completion(prompt)
        else:
            logger.error("[PCO] Unknown LLM provider interface.")
            return context
            
        # Strip markdown json block manually
        updated_text = updated_text.strip()
        if updated_text.startswith("```json"):
            updated_text = updated_text[7:]
        if updated_text.startswith("```"):
            updated_text = updated_text[3:]
        if updated_text.endswith("```"):
            updated_text = updated_text[:-3]

        parsed = json.loads(updated_text)
        
        # --- Memory Compression Logic ---
        # If memory log exceeds 30 items, compress the oldest 15 items
        mem_log = parsed.get("memory_log", [])
        if isinstance(mem_log, list) and len(mem_log) > 30:
            oldest_15 = mem_log[:15]
            recent_remaining = mem_log[15:]
            
            # Fire an asynchronous DB task to compress these
            new_summary = await compress_old_memory(oldest_15)
            
            # Merge with existing
            current_summary = parsed.get("compressed_summary", "")
            merged = f"{current_summary}\n\n{new_summary}".strip()
            
            parsed["compressed_summary"] = merged
            parsed["memory_log"] = recent_remaining

        # Run through schema validation inline before returning
        AgentContextSchema(**parsed)
        
        return parsed
    except json.JSONDecodeError:
        logger.error(f"[PCO] LLM failed to return valid JSON.")
        return context
    except ValidationError as e:
        logger.error(f"[PCO] LLM generated invalid structure: {e}")
        return context
    except Exception as e:
        logger.error(f"[PCO] Exception in update_context: {e}")
        return context
