"""
backend/llm/ollama_provider.py (V4)

Robust Ollama provider:
- Model is configurable (auto-selected by auto_provider)
- Converts OpenAI-style message list to Ollama prompt format
- Better error handling with timeout and connection error catches
"""

import json
import logging
import os
import requests
from backend.llm.base import LLMProvider

logger = logging.getLogger(__name__)

OLLAMA_BASE = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")


class OllamaProvider(LLMProvider):

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        logger.info("OllamaProvider ready — model: %s  endpoint: %s", model, OLLAMA_BASE)

    def _messages_to_ollama(self, messages: list) -> list:
        """Convert OpenAI-style messages to Ollama chat format."""
        ollama_msgs = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                # Ollama chat supports system role
                ollama_msgs.append({"role": "system", "content": content})
            elif role == "assistant":
                ollama_msgs.append({"role": "assistant", "content": content})
            else:
                ollama_msgs.append({"role": "user", "content": content})
        return ollama_msgs

    def generate(self, messages: list) -> str:
        ollama_msgs = self._messages_to_ollama(messages)
        try:
            res = requests.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": self.model, "messages": ollama_msgs, "stream": False},
                timeout=120,
            )
            res.raise_for_status()
            data = res.json()
            return data.get("message", {}).get("content", "")
        except requests.ConnectionError:
            logger.error("Ollama: connection refused — is Ollama running? (ollama serve)")
            return "[Error: Ollama not running. Start with: ollama serve]"
        except requests.Timeout:
            logger.error("Ollama: request timed out after 120s")
            return "[Error: Ollama timed out]"
        except Exception as e:
            logger.error("Ollama generate error: %s", e)
            return f"[Error: {e}]"

    def stream(self, messages: list):
        ollama_msgs = self._messages_to_ollama(messages)
        try:
            res = requests.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": self.model, "messages": ollama_msgs, "stream": True},
                stream=True,
                timeout=120,
            )
            res.raise_for_status()
            for line in res.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode())
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except Exception:
                        yield line.decode()
        except requests.ConnectionError:
            yield "[Error: Ollama not running. Start with: ollama serve]"
        except Exception as e:
            yield f"[Error: {e}]"
