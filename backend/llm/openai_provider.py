from openai import OpenAI
from backend.llm.base import LLMProvider

try:
    client = OpenAI()
except Exception:
    client = None

class OpenAIProvider(LLMProvider):

    def _normalize(self, messages):
        import json
        fixed = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, (dict, list)):
                content = json.dumps(content)
            fixed.append({"role": m.get("role"), "content": str(content)})
        return fixed

    def generate(self, messages):
        if not client:
            return "OpenAI client not initialized"
        clean_messages = self._normalize(messages)
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=clean_messages
        )
        return res.choices[0].message.content

    def stream(self, messages):
        if not client:
            yield "OpenAI client not initialized"
            return
        clean_messages = self._normalize(messages)
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=clean_messages,
            stream=True
        )
        for chunk in stream:
            yield chunk.choices[0].delta.content or ""
