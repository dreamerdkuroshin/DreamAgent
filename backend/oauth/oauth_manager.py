"""
backend/oauth/oauth_manager.py

The core OAuth engine orchestrating the generic provider flow.
Handles provider routing, secure storage, encryption, token retrieval,
key versioning, and transparent refresh.
"""
import os
import json
import logging
from datetime import datetime
from fastapi import HTTPException
from cryptography.fernet import Fernet
from typing import Optional

from backend.core.database import SessionLocal
from backend.core.models import OAuthToken
from .providers.google import GoogleOAuth
from .providers.microsoft import MicrosoftOAuth
from .providers.slack import SlackOAuth
from .providers.notion import NotionOAuth

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Provider Registry
# ──────────────────────────────────────────────────────────────────────────────
PROVIDERS = {
    "google": GoogleOAuth(),
    "microsoft": MicrosoftOAuth(),
    "slack": SlackOAuth(),
    "notion": NotionOAuth()
}

def get_provider(name: str):
    if name not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Provider {name} not supported.")
    return PROVIDERS[name]


# ──────────────────────────────────────────────────────────────────────────────
# Key Versioning — supports rotation without bricking old tokens
# ──────────────────────────────────────────────────────────────────────────────
KEY_VERSION = "v1"

# Prefer OAUTH_ENCRYPTION_KEY, fall back to ENCRYPTION_KEY (legacy) or auto-generate
_key = os.getenv("OAUTH_ENCRYPTION_KEY") or os.getenv("ENCRYPTION_KEY")
if not _key:
    _key = Fernet.generate_key().decode()
    os.environ["OAUTH_ENCRYPTION_KEY"] = _key
    logger.warning(
        "[OAuth] No OAUTH_ENCRYPTION_KEY found — generated an ephemeral key. "
        "Set OAUTH_ENCRYPTION_KEY in .env to persist tokens across restarts."
    )

_fernet = Fernet(_key.encode() if isinstance(_key, str) else _key)


def _encrypt(text: str) -> str:
    if not text:
        return ""
    return _fernet.encrypt(text.encode()).decode()


def _decrypt(encrypted: str) -> str:
    if not encrypted:
        return ""
    try:
        return _fernet.decrypt(encrypted.encode()).decode()
    except Exception as e:
        logger.error(f"[OAuth] Decryption failed: {e}")
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Token Persistence
# ──────────────────────────────────────────────────────────────────────────────

def save_tokens(provider: str, user_id: str, bot_id: str, tokens: dict):
    """
    Securely stores OAuth tokens scoped to the exact user + bot combo.
    
    Full schema stored:
      access_token, refresh_token, expires_at, scope, provider, user_id, bot_id
    
    Key versioning: the encrypted raw payload embeds key_version so future
    key rotations don't silently break decryption.
    
    Refresh-token safety: if the provider omits refresh_token on re-auth
    (Google only sends it on first consent), we retain the previously saved one.
    """
    with SessionLocal() as db:
        record = db.query(OAuthToken).filter_by(
            service=provider,
            user_id=user_id,
            bot_id=bot_id
        ).first()

        acc = _encrypt(tokens.get("access_token") or "")
        new_ref = tokens.get("refresh_token", "")
        exp_ts = tokens.get("expires_at", 0)
        scope = tokens.get("scope", "")

        # Build versioned payload for raw storage
        versioned_payload = {
            "key_version": KEY_VERSION,
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_at": exp_ts,
            "scope": scope,
            "provider": provider,
            "user_id": user_id,
            "bot_id": bot_id,
            **tokens.get("raw", {}),
        }

        if record:
            record.access_token = acc
            # ✅ Refresh-token safety: only overwrite if provider returned a new one
            if new_ref:
                record.refresh_token = _encrypt(new_ref)
            record.expires_at = datetime.fromtimestamp(exp_ts) if exp_ts else None
            record.scope = scope
            record.provider = provider
            record.key_version = KEY_VERSION
            record.token_json = _encrypt(json.dumps(versioned_payload))
        else:
            record = OAuthToken(
                service=provider,
                user_id=user_id,
                bot_id=bot_id,
                access_token=acc,
                refresh_token=_encrypt(new_ref) if new_ref else "",
                expires_at=datetime.fromtimestamp(exp_ts) if exp_ts else None,
                scope=scope,
                provider=provider,
                key_version=KEY_VERSION,
                token_json=_encrypt(json.dumps(versioned_payload))
            )
            db.add(record)

        db.commit()
        logger.info(f"[OAuth] Tokens saved for provider={provider} user={user_id} bot={bot_id} scope='{scope}'")


# ──────────────────────────────────────────────────────────────────────────────
# Token Retrieval + Auto-Refresh
# ──────────────────────────────────────────────────────────────────────────────

async def get_active_token(user_id: str, bot_id: str, provider: str) -> Optional[str]:
    """
    Retrieves and automatically refreshes tokens if expired (or within 5-min buffer).
    Returns None if no token exists or refresh fails (caller should trigger re-auth).
    """
    with SessionLocal() as db:
        record = db.query(OAuthToken).filter_by(
            service=provider,
            user_id=user_id,
            bot_id=bot_id
        ).first()

        if not record or not record.access_token:
            logger.info(f"[OAuth] No token found for provider={provider} user={user_id}")
            return None

        # Check expiration with 5-min safety buffer
        now_ts = datetime.utcnow().timestamp()
        expires_ts = record.expires_at.timestamp() if record.expires_at else 0

        if expires_ts < (now_ts + 300):
            logger.info(f"[OAuth] Token expired/expiring for {provider} — attempting refresh")
            oauth_engine = get_provider(provider)
            refresh_token = _decrypt(record.refresh_token or "")

            if not refresh_token:
                logger.warning(f"[OAuth] No refresh token for {provider} — user must re-authenticate")
                return None

            try:
                new_tokens = await oauth_engine.refresh_access_token(refresh_token)
                record.access_token = _encrypt(new_tokens.get("access_token", ""))
                new_exp = new_tokens.get("expires_at", 0)
                record.expires_at = datetime.fromtimestamp(new_exp) if new_exp else None
                record.key_version = KEY_VERSION
                db.commit()
                logger.info(f"[OAuth] Token refreshed successfully for {provider}")
            except Exception as e:
                logger.error(f"[OAuth] Refresh failed for {provider}: {e}")
                return None

        return _decrypt(record.access_token)


def has_token(user_id: str, bot_id: str, provider: str) -> bool:
    """Quick synchronous check whether a valid (non-expired) token exists."""
    with SessionLocal() as db:
        record = db.query(OAuthToken).filter_by(
            service=provider,
            user_id=user_id,
            bot_id=bot_id
        ).first()
        if not record or not record.access_token:
            return False
        # Consider a token valid if it hasn't expired yet (5-min buffer)
        if record.expires_at:
            return record.expires_at.timestamp() > (datetime.utcnow().timestamp() + 300)
        return bool(record.access_token)
