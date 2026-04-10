"""
backend/oauth/advanced_config.py

Phase 1 — Backend-only "Bring Your Own OAuth" endpoint.

Allows developer-mode users to upload a Google client_secret.json file.
Extracts only client_id + client_secret, encrypts per-user, and stores them.
Enforces:
  • Scope whitelist (Gmail, Calendar, Drive, YouTube)
  • Domain validation on redirect_uri
  • Encryption of stored credentials
"""
import os
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from cryptography.fernet import Fernet

from backend.core.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/oauth/advanced", tags=["oauth-advanced"])

# ──────────────────────────────────────────────────────────────────────────────
# Scope whitelist — only these scope *families* are permitted
# ──────────────────────────────────────────────────────────────────────────────
ALLOWED_SCOPE_PREFIXES = [
    "https://www.googleapis.com/auth/gmail",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/youtube",
    "openid",
    "email",
    "profile",
]

BLOCKED_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/admin",
    "https://www.googleapis.com/auth/apps",
    "https://www.googleapis.com/auth/iam",
    "https://www.googleapis.com/auth/compute",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/logging",
]

# ──────────────────────────────────────────────────────────────────────────────
# Per-user encryption (uses the same app-wide Fernet key)
# ──────────────────────────────────────────────────────────────────────────────
_key = os.getenv("OAUTH_ENCRYPTION_KEY") or os.getenv("ENCRYPTION_KEY")
if not _key:
    _key = Fernet.generate_key().decode()
_fernet = Fernet(_key.encode() if isinstance(_key, str) else _key)


def _encrypt_value(text: str) -> str:
    return _fernet.encrypt(text.encode()).decode()


def _decrypt_value(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()


# ──────────────────────────────────────────────────────────────────────────────
# In-memory store (Phase 1) – production would use a DB table
# ──────────────────────────────────────────────────────────────────────────────
_ADVANCED_CONFIGS: dict = {}   # user_id -> {encrypted_client_id, encrypted_client_secret, scopes}


def _validate_scopes(scopes: List[str]):
    """Reject any scope not in the whitelist or explicitly blocked."""
    for scope in scopes:
        scope_lower = scope.lower().strip()
        # Explicit block check
        for blocked in BLOCKED_SCOPES:
            if scope_lower.startswith(blocked.lower()):
                raise HTTPException(
                    status_code=403,
                    detail=f"🚫 Scope '{scope}' is blocked for security reasons. "
                           f"Administrative and infrastructure scopes are not permitted."
                )
        # Whitelist check
        if not any(scope_lower.startswith(prefix.lower()) for prefix in ALLOWED_SCOPE_PREFIXES):
            raise HTTPException(
                status_code=403,
                detail=f"🚫 Scope '{scope}' is not in the allowed list. "
                       f"Only Gmail, Calendar, Drive, YouTube, and OpenID scopes are permitted."
            )


def _validate_redirect_uri(redirect_uri: str):
    """Ensure redirect_uri matches the configured frontend domain."""
    allowed_domain = os.getenv("FRONTEND_DOMAIN", "http://localhost")
    backend_domain = os.getenv("BACKEND_DOMAIN", "http://localhost:8001")

    allowed_origins = [allowed_domain, backend_domain, "http://localhost", "http://127.0.0.1"]

    if not any(redirect_uri.startswith(origin) for origin in allowed_origins):
        raise HTTPException(
            status_code=400,
            detail=f"❌ Invalid redirect_uri: '{redirect_uri}'. "
                   f"Must match your configured domain to prevent token hijacking."
        )


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_client_secret(
    file: UploadFile = File(...),
    user_id: str = Form("local_user"),
    scopes: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
):
    """
    Accept a Google client_secret.json upload.
    
    Does NOT store the raw file.  Extracts only client_id + client_secret,
    encrypts them per-user, and validates scopes + redirect_uri.
    """
    # 1. Parse the uploaded JSON
    try:
        raw = await file.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")

    # 2. Extract credentials from Google's client_secret.json format
    #    Handles both {"installed": {...}} and {"web": {...}} formats
    inner = data.get("installed") or data.get("web") or data
    client_id = inner.get("client_id")
    client_secret = inner.get("client_secret")
    json_redirect_uri = (inner.get("redirect_uris") or [None])[0]

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail="Missing client_id or client_secret in the uploaded JSON."
        )

    # 3. Validate scopes
    requested_scopes = []
    if scopes:
        requested_scopes = [s.strip() for s in scopes.split(",") if s.strip()]
    else:
        # Default safe scopes
        requested_scopes = [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/youtube.readonly",
            "openid", "email", "profile",
        ]
    _validate_scopes(requested_scopes)

    # 4. Validate redirect_uri
    final_redirect = redirect_uri or json_redirect_uri or "http://localhost:8001/api/v1/oauth/google/callback"
    _validate_redirect_uri(final_redirect)

    # 5. Encrypt & store (per-user, NOT raw JSON)
    _ADVANCED_CONFIGS[user_id] = {
        "encrypted_client_id": _encrypt_value(client_id),
        "encrypted_client_secret": _encrypt_value(client_secret),
        "scopes": requested_scopes,
        "redirect_uri": final_redirect,
    }

    logger.info(f"[Advanced OAuth] Stored custom config for user={user_id} (scopes={len(requested_scopes)})")

    return {
        "status": "saved",
        "user_id": user_id,
        "scopes": requested_scopes,
        "redirect_uri": final_redirect,
        "message": "✅ Custom OAuth credentials securely stored. Only client_id and client_secret were extracted."
    }


@router.get("/status")
def advanced_config_status(user_id: str = "local_user"):
    """Check whether a user has uploaded custom OAuth credentials."""
    if user_id in _ADVANCED_CONFIGS:
        cfg = _ADVANCED_CONFIGS[user_id]
        return {
            "configured": True,
            "scopes": cfg["scopes"],
            "redirect_uri": cfg["redirect_uri"],
        }
    return {"configured": False}


@router.delete("/remove")
def remove_advanced_config(user_id: str = "local_user"):
    """Remove custom OAuth credentials for a user."""
    if user_id in _ADVANCED_CONFIGS:
        del _ADVANCED_CONFIGS[user_id]
        logger.info(f"[Advanced OAuth] Removed custom config for user={user_id}")
        return {"status": "removed"}
    raise HTTPException(status_code=404, detail="No custom config found for this user.")


def get_custom_credentials(user_id: str) -> dict | None:
    """
    Returns decrypted custom credentials if the user has uploaded them.
    Used by the Google provider to override default app credentials.
    """
    cfg = _ADVANCED_CONFIGS.get(user_id)
    if not cfg:
        return None
    return {
        "client_id": _decrypt_value(cfg["encrypted_client_id"]),
        "client_secret": _decrypt_value(cfg["encrypted_client_secret"]),
        "scopes": cfg["scopes"],
        "redirect_uri": cfg["redirect_uri"],
    }
