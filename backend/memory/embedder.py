"""
backend/memory/embedder.py

Now acts as a lightweight proxy to the Universal Embedding Router,
which intelligently routes embedding requests to OpenAI, Gemini,
Cohere, HuggingFace, or Ollama to save costs and reduce latency.
"""
from typing import List
from backend.memory.embedding_selector import get_embedding as router_get_embedding

def get_embedding(text: str) -> List[float]:
    """Return embedding vector via the Universal Embedding Router."""
    return router_get_embedding(text)
