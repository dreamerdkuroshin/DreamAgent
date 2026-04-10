"""
backend/services/model_discovery.py
Handles the live verification of API keys against LLM providers,
normalizes the retrieved models, and caches them in the database.
Includes state machine tracking (SYNCING/READY/FAILED) and hash-based bloat protection.
"""

import httpx
import logging
import asyncio
import json
import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from backend.core.models import UserProvider, UserModelCache
from backend.core.security import decrypt_token
from backend.llm.universal_provider import _ALL_PROVIDERS

logger = logging.getLogger(__name__)

# Map the environment keys back to their provider IDs and base URLs
ENV_TO_PROVIDER = {
    env_key: (provider_id, base_url)
    for provider_id, base_url, env_key, _ in _ALL_PROVIDERS
}


def _infer_tags(model_id: str) -> str:
    """Infer feature tags based on common model naming conventions."""
    tags = ["Live"]
    lower_id = model_id.lower()
    
    if any(x in lower_id for x in ["pro", "4o", "70b", "large", "plus", "sonnet", "405b", "max", "o1"]):
        tags.append("Powerful")
    elif any(x in lower_id for x in ["mini", "flash", "8b", "small", "haiku", "lite"]):
        tags.append("Fast")
        
    if "coder" in lower_id or "code" in lower_id:
        tags.append("Code")
        
    return ",".join(tags)


def _normalize_models(raw_models: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Ensure resilient extraction of model IDs handling weird vendor schemas."""
    normalized = []
    seen = set()
    
    for m in raw_models:
        if not isinstance(m, dict): continue
            
        m_id = m.get("id") or m.get("name") or m.get("model")
        if not m_id or not isinstance(m_id, str): continue
            
        if m_id in seen: continue
        seen.add(m_id)
        
        normalized.append({
            "model_id": m_id,
            "label": m_id,
            "tags": _infer_tags(m_id)
        })
        
    # Sort for canonical hashing
    return sorted(normalized, key=lambda x: x["model_id"])


async def verify_and_sync_provider(db: Session, user_id: str, env_key: str, api_key_encrypted: str):
    """
    State-aware discovery task. Updates sync_status and skips writes if hash is unchanged.
    """
    provider_info = ENV_TO_PROVIDER.get(env_key)
    if not provider_info:
        return
        
    provider_id, base_url = provider_info
    
    # ── 1. Set State to SYNCING ──
    u_prov = db.query(UserProvider).filter(
        UserProvider.user_id == user_id,
        UserProvider.provider == provider_id
    ).first()
    
    if not u_prov:
        u_prov = UserProvider(
            user_id=user_id,
            provider=provider_id,
            api_key_encrypted=api_key_encrypted,
            sync_status="SYNCING"
        )
        db.add(u_prov)
    else:
        u_prov.sync_status = "SYNCING"
        u_prov.last_sync_error = None
    
    db.commit()

    # ── 2. Decrypt & Fetch ──
    raw_models = []
    is_verified = False
    error_msg = None
    
    try:
        # We need the raw token for the request
        # Note: In settings.py we save the encrypted version
        raw_token = decrypt_token(api_key_encrypted)
        
        if base_url:
            url = base_url.rstrip("/") + "/models"
            headers = {"Authorization": f"Bearer {raw_token}"}
            
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    is_verified = True
                    # Most OpenAI-compat APIs return {"data": [...]}
                    if "data" in data and isinstance(data["data"], list):
                        raw_models = data["data"]
                    elif isinstance(data, list):
                        raw_models = data
                else:
                    error_msg = f"HTTP {resp.status_code}: {resp.text[:100]}"
                    logger.warning(f"Provider {provider_id} verification failed: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Discovery error for {provider_id}: {e}")

    # ── 3. Normalize & Hash ──
    normalized_models = _normalize_models(raw_models)
    
    # Canonical hash to prevent DB bloat
    new_hash = hashlib.sha256(json.dumps(normalized_models, sort_keys=True).encode()).hexdigest() if normalized_models else None

    # ── 4. Final State Update ──
    if not is_verified:
        u_prov.sync_status = "FAILED"
        u_prov.last_sync_error = error_msg
        u_prov.is_verified = False
    else:
        u_prov.sync_status = "READY"
        u_prov.is_verified = True
        u_prov.last_checked = datetime.utcnow()
        
        # Only rewrite DB if models actually changed
        if new_hash != u_prov.models_hash:
            u_prov.models_hash = new_hash
            # Wipe old models
            db.query(UserModelCache).filter(UserModelCache.user_provider_id == u_prov.id).delete()
            # Insert freshly verified
            for m in normalized_models:
                db.add(UserModelCache(
                    user_provider_id=u_prov.id,
                    model_id=m["model_id"],
                    label=m["label"],
                    tags=m["tags"]
                ))
            logger.info(f"Updated models for {provider_id} (hash changed)")
        else:
            logger.info(f"Skipping model rewrite for {provider_id} (hash identical)")
            
    db.commit()
