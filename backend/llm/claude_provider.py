import anthropic
from backend.llm.base import LLMProvider

try:
    client = anthropic.Anthropic()
except Exception:
    client = None

class ClaudeProvider(LLMProvider):

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
            return "Claude client not initialized"
        clean_messages = self._normalize(messages)
        res = client.messages.create(
            model="claude-3-sonnet-20240229",
            messages=clean_messages,
            max_tokens=1000
        )
        return res.content[0].text

    def stream(self, messages):
        if not client:
            yield "Claude client not initialized"
            return
        clean_messages = self._normalize(messages)
        with client.messages.stream(
            model="claude-3-sonnet-20240229",
            messages=clean_messages,
            max_tokens=1000
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    yield event.delta.text
