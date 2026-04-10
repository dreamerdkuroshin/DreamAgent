from backend.llm.auto_provider import get_provider

def get_llm(provider: str = "auto"):
    """
    Get the requested LLM provider or fallback smartly if API keys are missing.
    """
    provider_name, llm_instance = get_provider(provider)
    return llm_instance
