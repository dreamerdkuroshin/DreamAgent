"""
backend/builder/router.py

Centralized routing triggers for the Builder agent.
These help the background chat worker to cleanly identify intents
without risking circular dependencies from the main builder init.
"""

from backend.builder.preference_parser import (
    is_builder_request,
    is_recall_trigger,
    is_update_request,
    is_continue_last
)

__all__ = [
    "is_builder_request",
    "is_recall_trigger", 
    "is_update_request",
    "is_continue_last"
]
