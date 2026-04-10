"""
backend/core/config.py (Hardened)
Fix #10: Added all provider API keys to Settings so they are validated at startup.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    PG_HOST: str = "localhost"
    PG_DB: str = "dreamagent"
    PG_USER: str = "postgres"
    PG_PASSWORD: str = "postgres"
    PG_PORT: str = "5432"

    # LLM Providers — all optional (empty = disabled)
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    XAI_API_KEY: str = ""
    MISTRAL_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""
    NIMO_API_KEY: str = ""
    ZHIPUAI_API_KEY: str = ""
    MINI_API_KEY: str = ""
    LLAMA_API_KEY: str = ""
    COHERES_API_KEY: str = ""
    JAMBA_API_KEY: str = ""
    KIMI_API_KEY: str = ""
    REPLIT_API_KEY: str = ""
    TOGETHER_API_KEY: str = ""
    ERNIE_API_KEY: str = ""

    # Feature flags
    REDIS_URL: str = ""
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


settings = Settings()
