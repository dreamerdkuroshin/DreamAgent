"""
backend/react.py (Fixed)

Fix #8: LLM calls are now run via asyncio.to_thread to avoid blocking the event loop.
"""
import asyncio
from backend.tools.registry import TOOLS, ALLOWED_TOOLS
from backend.llm.selector import get_llm


class ReActEngine:

    def __init__(self, provider="auto"):
        self.llm = get_llm(provider)

    async def run_async(self, prompt: str, max_steps: int = 5) -> str:
        """Async-safe version used by FastAPI routes."""
        context = prompt

        for step in range(max_steps):
            # Run sync LLM in thread to not block event loop
            response = await asyncio.to_thread(
                self.llm.generate,
                [{"role": "user", "content": context}]
            )

            if "ACTION:" in response:
                try:
                    action_line = [l for l in response.split('\n') if "ACTION:" in l][0]
                    action_str = action_line.split("ACTION:", 1)[1].strip()
                    tool_name, tool_input = action_str.split(":", 1)
                    tool_name = tool_name.strip()
                    tool_input = tool_input.strip()

                    if tool_name not in ALLOWED_TOOLS:
                        context += f"\nOBSERVATION: Tool '{tool_name}' not allowed"
                        continue

                    tool = TOOLS.get(tool_name)
                    if tool:
                        # Run tool in thread too if it does IO
                        observation = await asyncio.to_thread(tool.run, tool_input)
                        context += f"\nOBSERVATION: {observation}"
                    else:
                        context += "\nOBSERVATION: Tool not found"
                except Exception as e:
                    context += f"\nOBSERVATION: Error parsing action - {str(e)}"

            elif "FINAL:" in response:
                try:
                    final_line = [l for l in response.split('\n') if "FINAL:" in l][0]
                    return final_line.split("FINAL:", 1)[1].strip()
                except Exception:
                    return response.split("FINAL:", 1)[-1].strip()
            else:
                return response

        return "Max steps reached"

    def run(self, prompt: str, max_steps: int = 5) -> str:
        """Sync wrapper kept for backward compatibility."""
        return asyncio.run(self.run_async(prompt, max_steps))
