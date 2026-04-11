"""
backend/api/settings.py

POST /api/v1/settings/keys  — save one or more API keys.
GET  /api/v1/settings/keys  — return which keys are configured (masked).

Keys are persisted to:
  1. SQLite DB via auth_service (survives backend restarts)
  2. The root .env file (picked up on next full restart + dotenv reload)
  3. os.environ (live effect for current process)
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.core.database import get_session
from backend.services import auth_service
from backend.services.model_discovery import verify_and_sync_provider
from backend.core.security import encrypt_token
from backend.core.responses import success_response
from backend.core.mode import get_current_mode, set_mode_override, detect_mode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# Root .env path
ENV_FILE = Path(__file__).parent.parent.parent / ".env"

# All known env-var keys mapped to their friendly provider name
KNOWN_KEYS: Dict[str, str] = {
    # ── LLM Providers ─────────────────────────────────────────────
    "GEMINI_API_KEY":       "Google Gemini",
    "OPENAI_API_KEY":       "OpenAI",
    "CLAUDE_API_KEY":       "Anthropic / Claude",
    "ANTHROPIC_API_KEY":    "Anthropic (alt)",
    "GROQ_API_KEY":         "Groq",
    "DEEPSEEK_API_KEY":     "DeepSeek",
    "HUGGINGFACE_API_KEY":  "HuggingFace",
    "OPENROUTER_API_KEY":   "OpenRouter",
    "MISTRAL_API_KEY":      "Mistral",
    "QWEN_API_KEY":         "Qwen (Alibaba)",
    "NVIDIA_API_KEY":       "NVIDIA NIM",
    "XAI_API_KEY":          "xAI Grok",
    "PERPLEXITY_API_KEY":   "Perplexity",
    "COHERE_API_KEY":       "Cohere",
    "ZHIPUAI_API_KEY":      "Zhipu AI (GLM)",
    "MINIMAX_API_KEY":      "MiniMax",
    "IBM_API_KEY":          "IBM Granite [OpenRouter Only]",
    "AMAZON_API_KEY":       "Amazon Nova [OpenRouter Only]",
    "JAMBA_API_KEY":        "AI21 / Jamba",
    "REPLIT_API_KEY":       "Replit [OpenRouter Only]",
    "MIMO_API_KEY":         "Mimo [OpenRouter Only]",
    "HERMES_API_KEY":       "Hermes (NousResearch) [OpenRouter Only]",
    "KIMI_API_KEY":         "Kimi (Moonshot)",
    # ── Service / Tool API Keys ────────────────────────────────────
    "TAVILY_API_KEY":       "Tavily Search",
    "AHREFS_API_KEY":       "Ahrefs",
    "SUPABASE_URL":         "Supabase Database URL",
    "SUPABASE_ANON_KEY":    "Supabase Anon Key",
    "STRIPE_API_KEY":       "Stripe",
    "OLLAMA_BASE_URL":      "Ollama Base URL",
}


def _update_env_file(key: str, value: str) -> None:
    """Write or update a single KEY=value line in the .env file."""
    if not ENV_FILE.exists():
        ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
        return

    content = ENV_FILE.read_text(encoding="utf-8")
    # Replace existing line (handles both empty and non-empty values)
    pattern = rf"^({re.escape(key)}=).*$"
    new_line = f"{key}={value}"
    if re.search(pattern, content, flags=re.MULTILINE):
        content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
    else:
        # Append if key not present
        if not content.endswith("\n"):
            content += "\n"
        content += f"{new_line}\n"

    ENV_FILE.write_text(content, encoding="utf-8")


@router.post("/keys")
def save_keys(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_session)):
    """
    Accept a flat dict of { ENV_VAR_NAME: value, ... }.
    Saves each to the DB, live environment, and .env file.
    Additionally, tests the key against the provider API and caches returned models.
    """
    if not data:
        raise HTTPException(status_code=400, detail="No keys provided")

    saved = []
    skipped = []

    for key, value in data.items():
        # Skip obviously bad values
        if not isinstance(value, str) or not value.strip():
            skipped.append(key)
            continue

        value = value.strip()
        
        # 1. NEW: Encrypt the token immediately
        token_encrypted = encrypt_token(value)

        # 2. Persist to SQLite (Legacy ApiKey approach)
        try:
            auth_service.save_api_key(db, key, value) # Legacy still takes raw for now unless we refactor all fallbacks
        except Exception as e:
            logger.warning("DB save failed for %s: %s", key, e)

        # 3. Update live environment
        os.environ[key] = value

        # 4. Persist to .env file
        try:
            _update_env_file(key, value)
        except Exception as e:
            logger.warning(".env update failed for %s: %s", key, e)
            
        # 5. Asynchronously Discover and Sync live models mapping to the active UserProvider
        import asyncio
        user_id = "local_user"
        background_tasks.add_task(
            lambda k, v_enc: asyncio.run(verify_and_sync_provider(db, user_id, k, v_enc)),
            key, token_encrypted
        )

        saved.append(key)
        logger.info("Saved key: %s (Syncing model discovery in background)", key)

    return success_response({"saved": saved, "skipped": skipped})


@router.get("/keys")
def get_keys(db: Session = Depends(get_session)):
    """
    Return configured key status for all known providers.
    Values are masked; only presence is returned.
    """
    result = {}
    for env_key, name in KNOWN_KEYS.items():
        # Check live env first, then DB
        val = os.getenv(env_key, "").strip()
        if not val:
            db_val = auth_service.get_api_key(db, env_key)
            val = db_val or ""

        # Using improved validation handler
        is_set = bool(
            val 
            and not val.startswith("${") 
            and val.strip() != "" 
            and val.upper() not in ("ENV", "YOUR_API_KEY", "YOUR-API-KEY-HERE", "PLACEHOLDER", "NONE", "NULL")
        )
        result[env_key] = {
            "name": name,
            "configured": is_set,
            "preview": (val[:4] + "••••" + val[-4:]) if is_set and len(val) > 8 else ("••••" if is_set else ""),
        }

    return success_response(result)

@router.get("/mode")
def get_mode_api():
    from backend.core.mode import _manual_override
    mode_name = detect_mode()
    return success_response({"mode_name": mode_name, "config": get_current_mode(), "override": _manual_override or "auto"})

@router.post("/mode")
def set_mode_api(data: dict):
    from backend.core.mode import _manual_override
    if "mode" in data:
        set_mode_override(data["mode"])
        return success_response({"status": "mode_updated", "mode_name": detect_mode(), "override": _manual_override or "auto"})
    raise HTTPException(status_code=400, detail="Must provide 'mode' key")
