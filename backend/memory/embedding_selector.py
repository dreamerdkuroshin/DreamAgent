import os
import requests
import logging
from typing import List

logger = logging.getLogger(__name__)

class UniversalEmbedding:
    """
    Routs embedding requests intelligently:
    1. OpenAI (text-embedding-3-small)
    2. Gemini (text-embedding-004)
    3. Cohere (embed-english-v3.0)
    4. SentenceTransformers (all-MiniLM-L6-v2) - Local CPU
    5. Ollama (nomic-embed-text) - Local AI
    """
    
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.cohere_key = os.getenv("COHERE_API_KEY", "")
        self.ollama_host = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # Validation for placeholder keys
        def is_valid(k):
            return k and "your" not in k.lower() and len(k) > 10
            
        self.use_openai = is_valid(self.openai_key)
        self.use_gemini = is_valid(self.gemini_key)
        self.use_cohere = is_valid(self.cohere_key)

        # Lazy load local transformer so we don't block boot time
        self._local_model = None
        self._local_failed = False

    def embed(self, text: str) -> List[float]:
        # Clean text
        text = text.replace("\n", " ").strip()
        if not text:
            return [0.0] * 384
            
        # 1. Try OpenAI
        if self.use_openai:
            try:
                resp = requests.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"},
                    json={"input": text, "model": "text-embedding-3-small"},
                    timeout=5
                )
                if resp.status_code == 200:
                    return resp.json()["data"][0]["embedding"]
            except Exception as e:
                logger.warning(f"[Embedder] OpenAI failed: {e}")

        # 2. Try Gemini
        if self.use_gemini:
            try:
                resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={self.gemini_key}",
                    headers={"Content-Type": "application/json"},
                    json={"model": "models/text-embedding-004", "content": {"parts": [{"text": text}]}},
                    timeout=5
                )
                if resp.status_code == 200:
                    return resp.json()["embedding"]["values"]
            except Exception as e:
                logger.warning(f"[Embedder] Gemini failed: {e}")

        # 3. Try Cohere
        if self.use_cohere:
            try:
                resp = requests.post(
                    "https://api.cohere.ai/v1/embed",
                    headers={"Authorization": f"Bearer {self.cohere_key}", "Content-Type": "application/json"},
                    json={"texts": [text], "model": "embed-english-v3.0", "input_type": "search_document"},
                    timeout=5
                )
                if resp.status_code == 200:
                    return resp.json()["embeddings"][0]
            except Exception as e:
                logger.warning(f"[Embedder] Cohere failed: {e}")

        # 4. Try Ollama (Local)
        try:
            resp = requests.post(
                f"{self.ollama_host}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=3
            )
            if resp.status_code == 200:
                return resp.json()["embedding"]
        except Exception as e:
            pass # Silent fail since Ollama might not be running

        # 5. Try HuggingFace SentenceTransformer (Local Python fallback)
        if not self._local_failed:
            if self._local_model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
                    logger.info("[Embedder] Local SentenceTransformer loaded.")
                except Exception as e:
                    self._local_failed = True
                    logger.warning(f"[Embedder] Local fallback failed: {e}")
                    
            if self._local_model is not None:
                try:
                    return self._local_model.encode(text).tolist()
                except Exception:
                    pass

        logger.error("[Embedder] ALL providers failed! Returning zero vector.")
        return [0.0] * 384 # Fallback vector so DB doesn't crash

# Singleton router instance
router = UniversalEmbedding()

def get_embedding(text: str) -> List[float]:
    return router.embed(text)
