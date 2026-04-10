import requests
import json
import logging
import os
from backend.llm.base import LLMProvider

logger = logging.getLogger(__name__)

class GeminiProvider(LLMProvider):
    """Google Gemini LLM Provider — uses Gemini REST API directly."""

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = model if model else "gemini-2.0-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        key_preview = f"{self.api_key[:8]}..." if self.api_key else "MISSING"
        logger.info(f"GeminiProvider initialized — model: {self.model} key: {key_preview}")

    def _build_contents(self, messages: list) -> list:
        """Convert OpenAI-style messages to Gemini 'contents' format."""
        contents = []
        for m in messages:
            role = "model" if m.get("role") == "assistant" else "user"
            content = m.get("content", "")
            if isinstance(content, (dict, list)):
                content = json.dumps(content)
            else:
                content = str(content)
            contents.append({"role": role, "parts": [{"text": content}]})
        return contents

    def generate(self, messages: list) -> str:
        if not self.api_key:
            return "Error: GEMINI_API_KEY not set"

        contents = self._build_contents(messages)
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        logger.info(f"[Gemini] POST generateContent model={self.model}")

        import time
        for attempt in range(3):
            try:
                resp = requests.post(url, json={"contents": contents}, timeout=60)
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"[Gemini] Rate limited (429). Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                if not resp.ok:
                    error_text = resp.text[:300]
                    logger.error(f"[Gemini] HTTP {resp.status_code}: {error_text}")
                    return f"Error: Gemini HTTP {resp.status_code} — {error_text}"

                data = resp.json()
                # Gemini REST format: candidates[0].content.parts[0].text
                # (NOT OpenAI format choices[0].message.content)
                candidates = data.get("candidates", [])
                if not candidates:
                    error_msg = data.get("error", {}).get("message", "No candidates in response")
                    logger.error(f"[Gemini] No candidates: {error_msg}")
                    return f"Error: {error_msg}"
                return candidates[0]["content"]["parts"][0]["text"]

            except Exception as e:
                logger.error(f"[Gemini] Attempt {attempt+1}/3 exception: {e}")
                if attempt == 2:
                    return f"Error: {e}"
                import time as _t
                _t.sleep(1)

        return "Error: Maximum retries exceeded"

    def stream(self, messages: list):
        """Use Gemini's streamGenerateContent endpoint for real streaming."""
        if not self.api_key:
            yield "Error: GEMINI_API_KEY not set"
            return

        contents = self._build_contents(messages)
        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?key={self.api_key}&alt=sse"

        try:
            resp = requests.post(url, json={"contents": contents}, stream=True, timeout=120)
            if not resp.ok:
                yield f"Error: Gemini HTTP {resp.status_code} — {resp.text[:200]}"
                return
            for line in resp.iter_lines():
                if line:
                    line_text = line.decode("utf-8")
                    if line_text.startswith("data: "):
                        try:
                            chunk = json.loads(line_text[6:])
                            text = chunk["candidates"][0]["content"]["parts"][0]["text"]
                            if text:
                                yield text
                        except Exception:
                            continue
        except Exception as e:
            yield f"Error: {e}"
