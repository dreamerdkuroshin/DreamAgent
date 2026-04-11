"""
integrations/supabase_client.py

Supabase integration for DreamAgent.
Provides auth, database (PostgREST), storage and realtime channels.

Setup:
    pip install supabase

Usage:
    from integrations.supabase_client import get_supabase
    sb = get_supabase()
    data = sb.table("agents").select("*").execute()
"""

import os
import logging
from functools import lru_cache
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

_supabase_instance = None


class SupabaseClient:
    """
    Thin wrapper around the Supabase Python SDK.
    Falls back gracefully if supabase package not installed.
    """

    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        try:
            from supabase import create_client, Client  # type: ignore
            self._client: Client = create_client(self.url, self.key)
            self._available = True
            logger.info("[Supabase] ✅ Connected to Supabase successfully.")
        except ImportError:
            logger.warning(
                "[Supabase] ⚠️  'supabase' package not installed. "
                "Run: pip install supabase"
            )
        except Exception as e:
            logger.error(f"[Supabase] ❌ Connection failed: {e}")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def client(self):
        return self._client

    # ── Database helpers ───────────────────────────────────────────────

    def select(self, table: str, columns: str = "*", filters: Optional[Dict] = None):
        """Select rows from a Supabase table."""
        if not self._available:
            return {"error": "Supabase not available", "data": []}
        try:
            query = self._client.table(table).select(columns)
            if filters:
                for col, val in filters.items():
                    query = query.eq(col, val)
            result = query.execute()
            return {"data": result.data, "count": len(result.data)}
        except Exception as e:
            logger.error(f"[Supabase] select error on {table}: {e}")
            return {"error": str(e), "data": []}

    def insert(self, table: str, data: Dict[str, Any]):
        """Insert a row into a table."""
        if not self._available:
            return {"error": "Supabase not available"}
        try:
            result = self._client.table(table).insert(data).execute()
            return {"data": result.data}
        except Exception as e:
            logger.error(f"[Supabase] insert error on {table}: {e}")
            return {"error": str(e)}

    def upsert(self, table: str, data: Dict[str, Any]):
        """Upsert a row into a table (insert or update on conflict)."""
        if not self._available:
            return {"error": "Supabase not available"}
        try:
            result = self._client.table(table).upsert(data).execute()
            return {"data": result.data}
        except Exception as e:
            logger.error(f"[Supabase] upsert error on {table}: {e}")
            return {"error": str(e)}

    def delete(self, table: str, filters: Dict[str, Any]):
        """Delete rows matching filters."""
        if not self._available:
            return {"error": "Supabase not available"}
        try:
            query = self._client.table(table).delete()
            for col, val in filters.items():
                query = query.eq(col, val)
            result = query.execute()
            return {"data": result.data}
        except Exception as e:
            logger.error(f"[Supabase] delete error on {table}: {e}")
            return {"error": str(e)}

    # ── Auth helpers ───────────────────────────────────────────────────

    def sign_up(self, email: str, password: str):
        """Register a new user via Supabase Auth."""
        if not self._available:
            return {"error": "Supabase not available"}
        try:
            result = self._client.auth.sign_up({"email": email, "password": password})
            return {"user": result.user, "session": result.session}
        except Exception as e:
            logger.error(f"[Supabase] sign_up error: {e}")
            return {"error": str(e)}

    def sign_in(self, email: str, password: str):
        """Sign in an existing user."""
        if not self._available:
            return {"error": "Supabase not available"}
        try:
            result = self._client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            return {"user": result.user, "session": result.session}
        except Exception as e:
            logger.error(f"[Supabase] sign_in error: {e}")
            return {"error": str(e)}

    def sign_out(self):
        """Sign out the current user."""
        if not self._available:
            return {"error": "Supabase not available"}
        try:
            self._client.auth.sign_out()
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def get_user(self):
        """Return the currently authenticated user."""
        if not self._available:
            return None
        try:
            return self._client.auth.get_user()
        except Exception:
            return None

    # ── Storage helpers ────────────────────────────────────────────────

    def upload_file(self, bucket: str, path: str, file_bytes: bytes, content_type: str = "application/octet-stream"):
        """Upload a file to Supabase Storage."""
        if not self._available:
            return {"error": "Supabase not available"}
        try:
            result = self._client.storage.from_(bucket).upload(
                path, file_bytes, {"content-type": content_type}
            )
            return {"path": path, "result": result}
        except Exception as e:
            logger.error(f"[Supabase] upload_file error: {e}")
            return {"error": str(e)}

    def get_public_url(self, bucket: str, path: str) -> str:
        """Get public URL for a stored file."""
        if not self._available:
            return ""
        try:
            return self._client.storage.from_(bucket).get_public_url(path)
        except Exception:
            return ""

    # ── Health check ──────────────────────────────────────────────────

    def ping(self) -> Dict[str, Any]:
        """Simple connectivity test."""
        if not self._available:
            return {"status": "unavailable", "reason": "supabase package not installed or wrong credentials"}
        try:
            # A lightweight call: fetch Supabase health endpoint info
            result = self._client.table("_health").select("*").limit(1).execute()
            return {"status": "ok", "url": self.url}
        except Exception as e:
            err_str = str(e)
            # PGRST205 = table not found → API is reachable and authenticated
            # Any PostgREST-style error means the Supabase REST API responded = connected
            pgrst_connected = (
                "PGRST" in err_str
                or "does not exist" in err_str
                or "relation" in err_str.lower()
                or "schema cache" in err_str.lower()
            )
            if pgrst_connected:
                return {"status": "ok", "url": self.url, "note": "connected (API responded, no _health table — normal)"}
            return {"status": "error", "detail": err_str}



@lru_cache(maxsize=1)
def get_supabase() -> SupabaseClient:
    """Get a singleton SupabaseClient from environment config."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        logger.warning("[Supabase] SUPABASE_URL or key not set in .env")
    return SupabaseClient(url=url, key=key)
