"""
backend/core/dragonfly_client.py  (v2 — delegates to DragonflyManager)

Legacy shim kept for backward compatibility.
All new code should import from dragonfly_manager instead.
"""
import logging

logger = logging.getLogger(__name__)

def get_dragonfly():
    """
    Return the live sync Redis/Dragonfly client, or None.
    Delegates to the self-healing DragonflyManager singleton.
    """
    from backend.core.dragonfly_manager import dragonfly
    return dragonfly.get_client()
