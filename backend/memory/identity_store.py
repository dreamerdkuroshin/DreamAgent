"""
backend/memory/identity_store.py

Agent Identity Memory.
Dedicated layer for identity, preferences, style, and goals.
Backed by Dragonfly for speed, persisted to SQLite as 'core' memory.
"""
import json
import logging
from typing import Dict, Any, List

from backend.core.dragonfly_manager import dragonfly

logger = logging.getLogger(__name__)

# Known identity fields
IDENTITY_KEYS = ["name", "style", "goal_short", "goal_long", "preferences", "dislike"]

class IdentityStore:
    def _get_client(self):
        return dragonfly.get_client()

    def get_profile(self, user_id: str, bot_id: str) -> Dict[str, Any]:
        """Fetch the full identity profile for this user."""
        client = self._get_client()
        if not client:
            return {}
            
        profile = {}
        try:
            for key in IDENTITY_KEYS:
                val = client.get(f"identity:{user_id}:{bot_id}:{key}")
                if val:
                    if isinstance(val, bytes):
                        val = val.decode('utf-8')
                    # Parse if json
                    try:
                        val = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    profile[key] = val
        except Exception as e:
            logger.error(f"[IdentityStore] Error fetching profile: {e}")
        
        return profile

    def update_field(self, user_id: str, bot_id: str, field: str, value: Any) -> bool:
        """Update a specific identity field."""
        if field not in IDENTITY_KEYS:
            logger.warning(f"[IdentityStore] Ignoring unknown identity field: {field}")
            return False
            
        client = self._get_client()
        if not client:
            return False
            
        try:
            val_str = json.dumps(value) if not isinstance(value, str) else value
            client.set(f"identity:{user_id}:{bot_id}:{field}", val_str)
            return True
        except Exception as e:
            logger.error(f"[IdentityStore] Error updating field {field}: {e}")
            return False

# Singleton
identity_store = IdentityStore()
