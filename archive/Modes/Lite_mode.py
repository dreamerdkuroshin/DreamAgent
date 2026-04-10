"""
Modes/Lite_mode.py
Lite mode — stateless single-turn inference, no memory.

Previous version: module-level `model = get_model(...)` was executed at import
time with `config.DEFAULT_LLM` (a plaintext global), initialising the model
adapter before the .env file was necessarily loaded.

This version resolves the model lazily on every call.
"""

from models.model_router import get_model
from config import DEFAULT_LLM


def run_Lite_mode(message: str) -> str:
    """Single-turn inference — no conversation history."""
    model = get_model(DEFAULT_LLM)
    return model.generate([{"role": "user", "content": message}])
