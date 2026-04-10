"""
backend/agents/structured_router.py

Forces the LLM to output structured JSON decisions:
  {"action": "chat" | "tool_name", "input": "..."}

This gives clean, reliable tool dispatch without text parsing heuristics.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, Callable
from backend.llm.universal_provider import UniversalProvider

logger = logging.getLogger(__name__)

ROUTER_SYSTEM = """\
You are a decision-making AI agent.

You MUST respond with ONLY valid JSON in this exact format:
{
  "action": "<action>",
  "input": "<input>"
}

Available actions:
- "chat"          → answer directly (normal question/conversation)
- "search_web"    → search the internet for current information
- "read_file"     → read and analyze a local file
- "run_code"      → execute Python code
- "shell"         → run a shell command (safe operations only)

Rules:
- If the user asks a general question → "chat"
- If the user needs live/current info → "search_web"
- If the user mentions a file/document → "read_file"
- If the user wants code run → "run_code"
- NEVER explain. NEVER add extra text. ONLY output JSON.
"""

# Map of action name → async handler function
# Each handler receives the `input` string and returns a string result
_TOOL_REGISTRY: Dict[str, Callable] = {}


def register_tool(name: str, handler: Callable):
    """Register a tool handler with the router."""
    _TOOL_REGISTRY[name] = handler
    logger.info(f"[Router] Registered tool: {name}")


def _extract_json(text: str) -> Optional[Dict]:
    """Try to extract JSON from LLM response even if wrapped in markdown."""
    # Try direct parse first
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # Try to extract from code block
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    # Try to find bare JSON object
    match = re.search(r'\{[^{}]*"action"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return None


class StructuredRouter:
    """
    Routes user queries to the right action via LLM JSON decision.
    Falls back to plain chat if parsing fails.
    """

    def __init__(self, provider: str = "auto", model: str = ""):
        self.llm = UniversalProvider(provider=provider, model=model)

    async def decide(self, query: str) -> Dict[str, Any]:
        """Ask the LLM what action to take. Returns parsed dict."""
        messages = [
            {"role": "system", "content": ROUTER_SYSTEM},
            {"role": "user", "content": query},
        ]
        try:
            raw = await self.llm.complete(
                f"{ROUTER_SYSTEM}\n\nUser query: {query}"
            )
            parsed = _extract_json(raw)
            if parsed and "action" in parsed:
                logger.info(f"[Router] Decision: {parsed}")
                return parsed
        except Exception as e:
            logger.warning(f"[Router] LLM decision failed: {e}")

        # Fallback: treat as plain chat
        return {"action": "chat", "input": query}

    async def route(self, query: str, publish=None) -> str:
        """
        Decide the action and either handle via tool or return for chat.
        Returns the result string (tool output or chat signal).
        """
        decision = await self.decide(query)
        action = decision.get("action", "chat")
        tool_input = decision.get("input", query)

        if action == "chat" or action not in _TOOL_REGISTRY:
            # Signal to caller to handle as normal chat
            return None

        # Execute registered tool
        if publish:
            publish({
                "type": "step",
                "content": f"🔧 Using tool: **{action}**",
                "agent": "router",
            })

        try:
            handler = _TOOL_REGISTRY[action]
            result = await handler(tool_input)
            return result
        except Exception as e:
            logger.error(f"[Router] Tool '{action}' failed: {e}")
            return f"Tool '{action}' failed: {e}"
