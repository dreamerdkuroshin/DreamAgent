"""
Modes/standard_mode.py
Standard mode — per-session memory, no shared global buffer.

Previous version: single module-level MemoryManager instance shared across
ALL calls to run_standard_mode().  Every user's messages ended up in the
same buffer, leaking conversation history across sessions.

This version creates a new MemoryManager per call so sessions are isolated.
"""

from memory.memory_manager import MemoryManager
from models.model_router import get_model
from config import DEFAULT_LLM


def run_standard_mode(message: str, session_id: str = "default") -> str:
    """
    Run a message through the standard LLM pipeline with per-session memory.

    Args:
        message:    User message.
        session_id: Caller-supplied session identifier for memory scoping.
                    Defaults to 'default' (single shared session) but callers
                    should pass a unique ID per user/conversation.
    """
    # Memory is scoped to session_id — different sessions never share a buffer.
    memory = MemoryManager(agent_id=f"standard:{session_id}")
    model  = get_model(DEFAULT_LLM)

    memory.store("user", message)
    history  = memory.retrieve()
    response = model.generate(history)
    memory.store("ai", response)
    return response


# Alias kept for backward compatibility
run_medium_mode = run_standard_mode
