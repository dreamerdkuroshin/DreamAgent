"""
backend/agents/base_agent.py

BaseAgent — the foundation all role-specific agents inherit from.
Provides a unified async `think()` method that wraps any synchronous
LLM provider via asyncio.to_thread so the event loop is never blocked.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for every role-specific agent.

    Args:
        llm:    Any LLM provider instance with a `.generate(messages)` method.
        memory: Optional MemoryAgent instance for context retrieval.
        tools:  List of tool callables available to this agent.
        role:   Human-readable role name used in trace events.
    """

    def __init__(
        self,
        llm,
        memory=None,
        tools: Optional[List[Any]] = None,
        role: str = "agent",
    ):
        self.llm = llm
        self.memory = memory
        self.tools = tools or []
        self.role = role

    async def think(self, prompt: str, system: str = "") -> str:
        """
        Send a prompt to the LLM and return its text response.
        Runs the synchronous provider in a thread to keep async safe.
        """
        if not self.llm:
            logger.error("No LLM provider configured for %s", self.role)
            return "Error: No LLM provider available."

        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(2):
            try:
                return await asyncio.to_thread(self.llm.generate, messages)
            except TimeoutError:
                if attempt == 0:
                    logger.warning("Timeout in %s. Retrying...", self.role)
                    continue
                else:
                    logger.error("LLM timeout failed in %s after retries.", self.role)
                    return f"Error: Timeout after retries."
            except Exception as exc:
                if type(exc).__name__ in ('TimeoutError', 'ReadTimeout', 'ConnectTimeout'):
                    if attempt == 0:
                        logger.warning("Network timeout in %s. Retrying...", self.role)
                        continue
                logger.error("LLM call failed in %s: %s", self.role, exc)
                return f"Error during generation: {exc}"
        return "Error during generation: Unexpected loop exit."
