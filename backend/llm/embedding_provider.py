import os
import aiohttp
import asyncio
import logging
from typing import List

logger = logging.getLogger(__name__)

async def get_embedding(text: str, provider: str = "local") -> List[float]:
    """
    Universal Embedding Router. 
    Routes text to the appropriate provider model. 
    Supported providers: local, openai, gemini.
    """
    provider = provider.lower()
    
    if provider == "openai":
        return await _openai_embed(text)
    elif provider == "gemini":
        return await _gemini_embed(text)
    else:
        # Default to local
        return await _local_embed(text)

async def _local_embed(text: str) -> List[float]:
    """Uses the sentence-transformers model loaded in document_processor."""
    try:
        from backend.memory.document_processor import get_query_embedding
        result = await asyncio.to_thread(get_query_embedding, text)
        return result
    except Exception as e:
        logger.error(f"[Embedding Router] Local embed failed: {e}")
        return []

async def _openai_embed(text: str) -> List[float]:
    """Calls OpenAI text-embedding-3-small. Returns 1536 elements."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("[Embedding Router] OPENAI_API_KEY not found. Falling back to local.")
        return await _local_embed(text)
        
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "input": text,
        "model": "text-embedding-3-small"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"[Embedding Router] OpenAI embed failed: {e}. Falling back to local.")
            return await _local_embed(text)

async def _gemini_embed(text: str) -> List[float]:
    """Calls Gemini text-embedding-004. Returns 768 elements."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("[Embedding Router] GEMINI_API_KEY not found. Falling back to local.")
        return await _local_embed(text)
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "models/text-embedding-004",
        "content": {
            "parts": [{"text": text}]
        }
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["embedding"]["values"]
        except Exception as e:
            logger.error(f"[Embedding Router] Gemini embed failed: {e}. Falling back to local.")
            return await _local_embed(text)
