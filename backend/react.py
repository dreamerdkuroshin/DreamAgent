"""
backend/react.py

Fixed: ReAct loop hardened with timeouts and failure recovery. (Task 4)
"""
import asyncio
import logging
from backend.tools.registry import TOOLS, ALLOWED_TOOLS
from backend.llm.selector import get_llm

logger = logging.getLogger(__name__)

class ReActEngine:

    def __init__(self, provider="auto"):
        self.llm = get_llm(provider)

    async def run_async(self, prompt: str, max_steps: int = 5) -> str:
        """Async-safe version used by FastAPI routes."""
        system_instruction = (
            "You are a tool-using AI worker. You must operate strictly in the following loop:\n"
            "THOUGHT: (your reasoning about what to do next)\n"
            "ACTION: tool_name: tool_input\n"
            "OBSERVATION: (the result of the action, provided by the system)\n\n"
            "When you have the final answer, output:\n"
            "FINAL: (your final response)\n"
        )
        context = f"{system_instruction}\n\nUSER PROMPT: {prompt}"
        
        tool_failures = 0
        max_failures = 3

        for step in range(max_steps):
            response = await asyncio.to_thread(
                self.llm.generate,
                [{"role": "user", "content": context}]
            )

            if "FINAL:" in response:
                try:
                    final_line = [l for l in response.split('\n') if "FINAL:" in l][0]
                    return final_line.split("FINAL:", 1)[1].strip()
                except Exception:
                    return response.split("FINAL:", 1)[-1].strip()

            elif "ACTION:" in response:
                try:
                    action_line = [l for l in response.split('\n') if "ACTION:" in l][0]
                    action_str = action_line.split("ACTION:", 1)[1].strip()
                    tool_name, tool_input = action_str.split(":", 1)
                    tool_name = tool_name.strip()
                    tool_input = tool_input.strip()

                    if tool_name not in ALLOWED_TOOLS:
                        context += f"\nOBSERVATION: Tool '{tool_name}' not allowed"
                        tool_failures += 1
                    else:
                        tool = TOOLS.get(tool_name)
                        if tool:
                            try:
                                # Run tool with a strict timeout (10 seconds)
                                observation = await asyncio.wait_for(
                                    asyncio.to_thread(tool.run, tool_input),
                                    timeout=10.0
                                )
                                context += f"\nOBSERVATION: {observation}"
                                tool_failures = 0 # reset on success
                            except asyncio.TimeoutError:
                                context += f"\nOBSERVATION: Execution of '{tool_name}' timed out after 10s."
                                tool_failures += 1
                            except Exception as e:
                                context += f"\nOBSERVATION: Tool execution error - {str(e)}"
                                tool_failures += 1
                        else:
                            context += f"\nOBSERVATION: Tool '{tool_name}' not found"
                            tool_failures += 1
                except Exception as e:
                    context += f"\nOBSERVATION: Error parsing action - {str(e)}"
                    tool_failures += 1
            else:
                # Malformed output, try to nudge it
                context += "\nOBSERVATION: Invalid format. You must use 'THOUGHT:', 'ACTION:', or 'FINAL:' prefixes."
                tool_failures += 1

            if tool_failures >= max_failures:
                logger.warning("ReActEngine hit max tool failures. Forcing fallback.")
                context += "\nOBSERVATION: You have failed to use tools correctly 3 times in a row. You must output FINAL: with whatever information you have or state that you cannot complete the task."

        return "Max steps reached"

    def run(self, prompt: str, max_steps: int = 5) -> str:
        """Sync wrapper kept for backward compatibility."""
        return asyncio.run(self.run_async(prompt, max_steps))
