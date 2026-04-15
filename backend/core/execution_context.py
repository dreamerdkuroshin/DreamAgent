"""
backend/core/execution_context.py

Provides ContextVars for tracking the current execution ID across async boundaries.
Allows tools to securely fetch the execution_id for idempotency without LLM hallucination.
"""
import contextvars
from typing import Optional

# Holds the current execution_id in format {task_id}:{node_id}
current_execution_id = contextvars.ContextVar('current_execution_id', default=None)

def set_execution_id(exec_id: str) -> contextvars.Token:
    """Sets the execution ID for the current async context."""
    return current_execution_id.set(exec_id)

def get_execution_id() -> Optional[str]:
    """Retrieves the active execution ID."""
    return current_execution_id.get()
