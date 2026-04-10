"""
backend/llm/auto_provider.py
Reconstructed from .pyc cache analysis.
Detects and returns the best available LLM provider.
"""
import os
import logging
from functools import lru_cache
from typing import Tuple
import requests

from backend.llm.base import LLMProvider

logger = logging.getLogger(__name__)

PROVIDER_CONFIG = {
    "deepseek":    ("https://api.deepseek.com",                        "DEEPSEEK_API_KEY",    "deepseek-chat"),
    "qwen":        ("https://dashscope.aliyuncs.com/compatible-mode/v1","QWEN_API_KEY",        "qwen-plus"),
    "groq":        ("https://api.groq.com/openai/v1",                  "GROQ_API_KEY",        "llama-3.3-70b-versatile"),
    "openrouter":  ("https://openrouter.ai/api/v1",                    "OPENROUTER_API_KEY",  "openai/gpt-4o"),
    "grokk":       ("https://api.x.ai/v1",                             "XAI_API_KEY",         "grok-2-1212"),
    "mistral":     ("https://api.mistral.ai/v1",                       "MISTRAL_API_KEY",     "mistral-large-latest"),
    "perplexity":  ("https://api.perplexity.ai",                       "PERPLEXITY_API_KEY",  "llama-3.1-sonar-large-128k-online"),
    "nimo":        ("https://integrate.api.nvidia.com/v1",             "NIMO_API_KEY",        "meta/llama-3.1-405b-instruct"),
    "zhipuai":     ("https://open.bigmodel.cn/api/paas/v4",            "ZHIPUAI_API_KEY",     "glm-4"),
    "minimax":     ("https://api.minimax.chat/v1",                     "MINI_API_KEY",        "abab6-chat"),
    "together":    ("https://api.together.xyz/v1",                     "LLAMA_API_KEY",       "meta-llama/Llama-3-70b-chat-hf"),
    "cohere":      ("https://api.cohere.ai/v1",                        "COHERES_API_KEY",     "command-r-plus"),
    "jamba":       ("https://api.ai21.com/studio/v1",                  "JAMBA_API_KEY",       "jamba-instruct-v1"),
    "kimi":        ("https://api.moonshot.cn/v1",                      "KIMI_API_KEY",        "moonshot-v1-8k"),
    "replit":      ("https://api.replit.com/v1",                       "REPLIT_API_KEY",      "replit-code-v1-3b"),
    "hermes":      ("https://api.together.xyz/v1",                     "TOGETHER_API_KEY",    "NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO"),
    "ernie":       ("https://qianfan.baidubce.com/v2",                 "ERNIE_API_KEY",       "ernie-4.0-8k"),
}


def _check_env(env_var: str) -> bool:
    """Return True only if the env var is set to a non-empty, non-placeholder value."""
    val = os.getenv(env_var, "").strip()
    return bool(val) and val.upper() not in ("ENV", "YOUR_API_KEY", "PLACEHOLDER", "NONE", "NULL")


def _ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200 and len(r.json().get("models", [])) > 0
    except Exception:
        return False


def _ollama_best_model() -> str:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        models = r.json().get("models", [])
        for m in models:
            if "llama3" in m["name"].lower():
                return m["name"]
        return models[0]["name"] if models else "llama3"
    except Exception:
        return "llama3"


def detect_provider() -> str:
    """Auto-detect the best available provider. Gemini checked first."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    logger.info(f"[Detect] GEMINI_API_KEY present: {bool(gemini_key)}")
    if _check_env("GEMINI_API_KEY"):
        logger.info("[Detect] -> gemini")
        return "gemini"

    ollama_ok = _ollama_available()
    logger.info(f"[Detect] OLLAMA_AVAILABLE: {ollama_ok}")
    if ollama_ok:
        logger.info("[Detect] -> ollama")
        return "ollama"

    for name, env_key in [("openai", "OPENAI_API_KEY"), ("claude", "ANTHROPIC_API_KEY"),
                           ("groq", "GROQ_API_KEY"), ("openrouter", "OPENROUTER_API_KEY")]:
        if _check_env(env_key):
            logger.info(f"[Detect] -> {name}")
            return name

    return "unavailable"


class RobustFallbackProvider(LLMProvider):
    """Wraps multiple providers and tries each up to 3 times before moving to the next."""
    def __init__(self, providers: list, name: str):
        self.providers = providers
        self.name = name

    def generate(self, messages: list) -> str:
        import time
        for p_idx, provider in enumerate(self.providers):
            for attempt in range(3):
                try:
                    res = provider.generate(messages)
                    if hasattr(res, "startswith") and res.startswith("Error:"):
                        raise RuntimeError(res)
                    return res
                except Exception as e:
                    logger.warning(f"[Fallback] Provider #{p_idx+1} Generate attempt {attempt+1}/3 failed: {e}")
                    time.sleep(1)
        return "Error: All providers exhausted after 3 attempts each."

    def stream(self, messages: list):
        import time
        for p_idx, provider in enumerate(self.providers):
            for attempt in range(3):
                try:
                    success = False
                    for token in provider.stream(messages):
                        if hasattr(token, "startswith") and token.startswith("Error:"):
                            raise RuntimeError(token)
                        success = True
                        yield token
                    if success:
                        return
                except Exception as e:
                    logger.warning(f"[Fallback] Provider #{p_idx+1} Stream attempt {attempt+1}/3 failed: {e}")
                    time.sleep(1)
                    if success:
                        # Failed mid-stream
                        return
        yield "Error: All providers exhausted after 3 attempts each."


def get_provider(requested: str = "auto", model: str = "") -> Tuple[str, LLMProvider]:
    """Return (provider_name, LLMProvider instance). Optional model override."""
    from backend.llm.ollama_provider import OllamaProvider
    from backend.llm.openai_provider import OpenAIProvider
    from backend.llm.claude_provider import ClaudeProvider
    from backend.llm.gemini_provider import GeminiProvider
    from backend.llm.universal_provider import UniversalProvider

    if requested in ("auto", ""):
        requested = detect_provider()

    primary_name = requested
    primary_provider = None

    if requested == "ollama":
        m = model or _ollama_best_model()
        primary_provider = OllamaProvider(model=m)
    elif requested == "openai":
        if not _check_env("OPENAI_API_KEY"):
            raise RuntimeError("API key OPENAI_API_KEY not set for openai")
        primary_provider = OpenAIProvider()
    elif requested == "claude":
        primary_provider = ClaudeProvider()
    elif requested == "gemini":
        m = model or "gemini-1.5-flash"
        primary_provider = GeminiProvider(model=m)
    elif requested in PROVIDER_CONFIG:
        url, env_key, default_model = PROVIDER_CONFIG[requested]
        api_key = os.getenv(env_key, "")
        if not _check_env(env_key):
            raise RuntimeError(f"API key {env_key} not set for {requested}")
        primary_provider = UniversalProvider(api_key=api_key, base_url=url, model=model or default_model)
    else:
        logger.warning(f"Unknown provider '{requested}' — falling back to auto-detect.")
        return get_provider("auto", model=model)

    fallback_list = [primary_provider]
    
    if primary_name != "openrouter" and _check_env("OPENROUTER_API_KEY"):
        fallback_list.append(UniversalProvider(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1", model="openai/gpt-4o"))
    if primary_name != "groq" and _check_env("GROQ_API_KEY"):
        fallback_list.append(UniversalProvider(api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1", model="llama-3.3-70b-versatile"))
    if primary_name != "gemini" and _check_env("GEMINI_API_KEY"):
        fallback_list.append(GeminiProvider(model="gemini-1.5-flash"))
        
    return primary_name, RobustFallbackProvider(fallback_list, primary_name)


def get_provider_name() -> str:
    return detect_provider()
