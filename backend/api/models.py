"""
backend/api/models.py
Returns only the LLM providers that have valid API keys configured.
Frontend uses this to populate the model selector dropdown.
"""
import os
import asyncio
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from backend.core.database import get_session
from backend.core.models import UserProvider, UserModelCache
from backend.services.model_discovery import verify_and_sync_provider
from backend.llm.universal_provider import _ALL_PROVIDERS
from backend.core.cache import cache_get, cache_set

router = APIRouter(prefix="/api/v1/models", tags=["models"])

MODELS_CACHE_KEY = "api:models:local_user"
MODELS_CACHE_TTL = 60  # seconds

def _key_set(env_var: str) -> str:
    val = os.getenv(env_var, "").strip()
    if bool(val) and val.upper() not in ("ENV", "YOUR_API_KEY", "PLACEHOLDER", "NONE", "NULL", ""):
        return val
    return ""

# All supported providers with their models and display info
ALL_PROVIDERS = [
    {
        "id": "gemini",
        "name": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "icon": "🌀",
        "models": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "tag": "Fast"},
            {"id": "gemini-1.5-pro",   "name": "Gemini 1.5 Pro",   "tag": "Powerful"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "tag": "Balanced"},
        ]
    },
    {
        "id": "groq",
        "name": "Groq",
        "env_key": "GROQ_API_KEY",
        "icon": "⚡",
        "models": [
            {"id": "llama3-70b-8192",          "name": "Llama 3 70B",       "tag": "Powerful"},
            {"id": "llama3-8b-8192",            "name": "Llama 3 8B",        "tag": "Fast"},
            {"id": "mixtral-8x7b-32768",        "name": "Mixtral 8x7B",      "tag": "Balanced"},
            {"id": "gemma2-9b-it",              "name": "Gemma 2 9B",        "tag": "Efficient"},
        ]
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "icon": "🔀",
        "models": [
            {"id": "openai/gpt-4o",                    "name": "GPT-4o",               "tag": "Powerful"},
            {"id": "anthropic/claude-3.5-sonnet",       "name": "Claude 3.5 Sonnet",    "tag": "Powerful"},
            {"id": "meta-llama/llama-3.1-70b-instruct", "name": "Llama 3.1 70B",        "tag": "Open"},
            {"id": "google/gemini-pro-1.5",             "name": "Gemini 1.5 Pro",       "tag": "Balanced"},
            {"id": "mistralai/mistral-large",           "name": "Mistral Large",        "tag": "Balanced"},
        ]
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "icon": "🤖",
        "models": [
            {"id": "gpt-4o",       "name": "GPT-4o",       "tag": "Powerful"},
            {"id": "gpt-4o-mini",  "name": "GPT-4o Mini",  "tag": "Fast"},
            {"id": "gpt-4-turbo",  "name": "GPT-4 Turbo",  "tag": "Balanced"},
        ]
    },
    {
        "id": "claude",
        "name": "Anthropic Claude",
        "env_key": "CLAUDE_API_KEY",
        "icon": "🧠",
        "models": [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "tag": "Powerful"},
            {"id": "claude-3-haiku-20240307",    "name": "Claude 3 Haiku",    "tag": "Fast"},
        ]
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "icon": "🔭",
        "models": [
            {"id": "deepseek-chat",    "name": "DeepSeek Chat",    "tag": "Balanced"},
            {"id": "deepseek-coder",   "name": "DeepSeek Coder",   "tag": "Code"},
        ]
    },
    {
        "id": "mistral",
        "name": "Mistral",
        "env_key": "MISTRAL_API_KEY",
        "icon": "🌬️",
        "models": [
            {"id": "mistral-large-latest",  "name": "Mistral Large",  "tag": "Powerful"},
            {"id": "mistral-small-latest",  "name": "Mistral Small",  "tag": "Fast"},
        ]
    },
    {
        "id": "qwen",
        "name": "Alibaba Qwen",
        "env_key": "QWEN_API_KEY",
        "icon": "🏵️",
        "models": [
            {"id": "qwen-max", "name": "Qwen Max", "tag": "Powerful"},
            {"id": "qwen-plus", "name": "Qwen Plus", "tag": "Balanced"},
            {"id": "qwen-turbo", "name": "Qwen Turbo", "tag": "Fast"},
        ]
    },
    {
        "id": "nvidia",
        "name": "NVIDIA",
        "env_key": "NVIDIA_API_KEY",
        "icon": "🟩",
        "models": [
            {"id": "nvidia/llama-3.1-405b", "name": "Llama 3.1 405B", "tag": "Massive"},
            {"id": "nvidia/nemotron-4-340b", "name": "Nemotron 4 340B", "tag": "Powerful"},
            {"id": "nvidia/mistral-nemo-12b", "name": "Mistral Nemo 12B", "tag": "Efficient"},
        ]
    },
    {
        "id": "xai",
        "name": "xAI Grok",
        "env_key": "XAI_API_KEY",
        "icon": "✖️",
        "models": [
            {"id": "grok-1", "name": "Grok 1", "tag": "Powerful"},
            {"id": "grok-beta", "name": "Grok Beta", "tag": "Experimental"},
        ]
    },
    {
        "id": "perplexity",
        "name": "Perplexity",
        "env_key": "PERPLEXITY_API_KEY",
        "icon": "🌐",
        "models": [
            {"id": "sonar-large", "name": "Sonar Large", "tag": "Search"},
            {"id": "sonar-medium", "name": "Sonar Medium", "tag": "Search"},
        ]
    },
    {
        "id": "cohere",
        "name": "Cohere",
        "env_key": "COHERES_API_KEY",
        "icon": "🏢",
        "models": [
            {"id": "command-r-plus", "name": "Command R+", "tag": "Enterprise"},
            {"id": "command-r", "name": "Command R", "tag": "Balanced"},
        ]
    },
    {
        "id": "zhipu",
        "name": "Zhipu AI",
        "env_key": "ZHIPUAI_API_KEY",
        "icon": "🌏",
        "models": [
            {"id": "glm-4", "name": "GLM-4", "tag": "Powerful"},
            {"id": "glm-4-9b", "name": "GLM-4 9B", "tag": "Efficient"},
        ]
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "env_key": "MINIMAX_API_KEY",
        "icon": "🎨",
        "models": [
            {"id": "abab6", "name": "Abab 6", "tag": "Powerful"},
            {"id": "abab5.5", "name": "Abab 5.5", "tag": "Balanced"},
        ]
    },
    {
        "id": "replit",
        "name": "Replit",
        "env_key": "REPLIT_API_KEY",
        "icon": "🌀",
        "models": [
            {"id": "code-v1-3b", "name": "Code V1 3B", "tag": "Code"},
        ]
    },
    {
        "id": "ibm",
        "name": "IBM Granite",
        "env_key": "IBM_API_KEY",
        "icon": "🟦",
        "models": [
            {"id": "granite-3.0-8b", "name": "Granite 3.0", "tag": "Enterprise"},
        ]
    },
    {
        "id": "amazon",
        "name": "Amazon Nova",
        "env_key": "AMAZON_API_KEY",
        "icon": "☁️",
        "models": [
            {"id": "amazon-nova-pro", "name": "Nova Pro", "tag": "Powerful"},
            {"id": "amazon-nova-lite", "name": "Nova Lite", "tag": "Fast"},
        ]
    },
    {
        "id": "jamba",
        "name": "AI21 Jamba",
        "env_key": "JAMBA_API_KEY",
        "icon": "🐘",
        "models": [
            {"id": "jamba-1.5-large", "name": "Jamba 1.5 Large", "tag": "Powerful"},
            {"id": "jamba-1.5-mini", "name": "Jamba 1.5 Mini", "tag": "Fast"},
        ]
    },
    {
        "id": "mimo",
        "name": "Mimo",
        "env_key": "MIMO_API_KEY",
        "icon": "📱",
        "models": [
            {"id": "mimo-large", "name": "Mimo Large", "tag": "Mobile"},
        ]
    },
    {
        "id": "hermes",
        "name": "Hermes",
        "env_key": "HERMES_API_KEY",
        "icon": "🏹",
        "models": [
            {"id": "hermes-3-llama-3.1", "name": "Hermes 3", "tag": "Specialized"},
        ]
    },
    {
        "id": "ollama",
        "name": "Ollama (Local)",
        "env_key": None,   # always shown if Ollama is running
        "icon": "🦙",
        "models": [
            {"id": "gemma3:4b",   "name": "Gemma 3 4B",   "tag": "Local"},
            {"id": "llama3",      "name": "Llama 3",       "tag": "Local"},
            {"id": "mistral",     "name": "Mistral",       "tag": "Local"},
            {"id": "codellama",   "name": "Code Llama",    "tag": "Local"},
        ]
    },
]


def _ollama_running() -> bool:
    try:
        import requests as req
        r = req.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


async def _fetch_models_for_provider(provider_dict: dict, api_key: str, base_url: str):
    default_models = provider_dict.get("models", [])
    if not base_url:
        return default_models
        
    try:
        url = base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and isinstance(data["data"], list):
                    fetched = []
                    # Keep some order: live models, limit to 100 to avoid giant UI payload
                    for model in sorted(data["data"], key=lambda x: x.get("id", ""), reverse=True)[:50]:
                        m_id = model.get("id")
                        if not m_id: continue
                        
                        # Add some heuristics for tags
                        tag = "Live"
                        id_lower = m_id.lower()
                        if "pro" in id_lower or "4o" in id_lower or "70b" in id_lower or "large" in id_lower or "plus" in id_lower or "sonnet" in id_lower:
                            tag = "Powerful"
                        elif "mini" in id_lower or "flash" in id_lower or "8b" in id_lower or "small" in id_lower or "haiku" in id_lower:
                            tag = "Fast"
                        elif "coder" in id_lower or "code" in id_lower:
                            tag = "Code"
                        
                        fetched.append({
                            "id": m_id,
                            "name": m_id,
                            "tag": tag
                        })
                    if fetched:
                        return fetched
    except Exception as e:
        import logging
        logging.warning(f"Failed to fetch models for {provider_dict['name']}: {e}")
        
    return default_models


@router.get("")
async def list_available_models(background_tasks: BackgroundTasks, db: Session = Depends(get_session)):
    """
    Returns only providers that have verified API keys in the DB.
    Reads directly from the UserModelCache scoped to the current user.
    Implements 24h auto-refresh and SYNCING deadlock protection.
    Results cached for 60s via Dragonfly.
    """
    # Fast path: cache hit
    cached = cache_get(MODELS_CACHE_KEY)
    if cached is not None:
        return cached

    user_id = "local_user"
    
    # Query all providers for this user
    user_providers = db.query(UserProvider).options(
        joinedload(UserProvider.models)
    ).filter(
        UserProvider.user_id == user_id
    ).all()
    
    active_providers = []
    
    for u_prov in user_providers:
        # --- 1. Deadlock & Stale Cache Protection ---
        should_refresh = False
        
        # If stuck in SYNCING for > 5 minutes, assume worker died and re-trigger
        if u_prov.sync_status == "SYNCING":
            if u_prov.last_checked and (datetime.utcnow() - u_prov.last_checked) > timedelta(minutes=5):
                should_refresh = True
        
        # If successfully synced but older than 24h, refresh background
        elif u_prov.sync_status == "READY":
            if u_prov.last_checked and (datetime.utcnow() - u_prov.last_checked) > timedelta(days=1):
                should_refresh = True
        
        # If pending or failed, we can also retry manually via background if requested
        
        if should_refresh:
            static_info = next((p for p in ALL_PROVIDERS if p["id"] == u_prov.provider), None)
            if static_info:
                background_tasks.add_task(
                    lambda k, v: asyncio.run(verify_and_sync_provider(db, user_id, k, v)),
                    static_info["env_key"], u_prov.api_key_encrypted
                )

        # --- 2. Build Response ---
        static_info = next((p for p in ALL_PROVIDERS if p["id"] == u_prov.provider), None)
        
        # We only show it in the list if it's READY. 
        # If it's SYNCING or FAILED, we send the status so the UI can show placeholders.
        provider_data = {
            "id": u_prov.provider,
            "name": static_info["name"] if static_info else u_prov.provider.capitalize(),
            "icon": static_info["icon"] if static_info else "🤖",
            "sync_status": u_prov.sync_status,
            "error": u_prov.last_sync_error,
            "models": []
        }
        
        if u_prov.sync_status == "READY":
            for m in u_prov.models:
                provider_data["models"].append({
                    "id": m.model_id,
                    "name": m.label,
                    "tag": m.tags.split(",")[0] if m.tags else ""
                })
            provider_data["models"] = sorted(provider_data["models"], key=lambda x: str(x.get("id", "")))
            
        active_providers.append(provider_data)

    # 3. Add Ollama (Local)
    if _ollama_running():
        ollama_static = next((p for p in ALL_PROVIDERS if p["id"] == "ollama"), None)
        if ollama_static:
            active_providers.append({
                "id": "ollama",
                "name": ollama_static["name"],
                "icon": ollama_static["icon"],
                "sync_status": "READY",
                "models": ollama_static["models"]
            })

    # Filter out empty or unverified ones unless they are currently syncing
    display_providers = [p for p in active_providers if p["sync_status"] in ["READY", "SYNCING"]]

    # 4. Defaults
    default_prov = None
    default_mod = None
    ready_ones = [p for p in display_providers if p["sync_status"] == "READY" and p["models"]]
    if ready_ones:
        default_prov = ready_ones[0]["id"]
        default_mod = ready_ones[0]["models"][0]["id"]

    result = {
        "providers": display_providers,
        "default_provider": default_prov,
        "default_model": default_mod,
    }
    cache_set(MODELS_CACHE_KEY, result, ttl=MODELS_CACHE_TTL)
    return result
