"""
backend/agents/executor.py

ExecutorAgent — executes a single task step, optionally using tools.
Subclassed by specialized agents (CodeAgent, SearchAgent, MathAgent).
"""
import logging
from typing import Any, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

EXECUTOR_SYSTEM = """You are a helpful AI assistant.

- Do NOT show steps
- Do NOT show execution summary
- Only give final answer
- Speak like ChatGPT
"""


class ExecutorAgent(BaseAgent):
    """Executes a single task step using the LLM (and optionally tools)."""

    def __init__(self, llm, memory=None, tools: Optional[List[Any]] = None):
        super().__init__(llm, memory, tools, role="executor")

    async def execute(self, step: str, context: str = "") -> str:
        """
        Execute a task step, optionally with prior context from previous steps.

        Args:
            step:    The task step description from the PlannerAgent.
            context: Accumulated results from previous steps (may be empty).

        Returns:
            String result for this step.
        """
        ctx_section = f"\n\nContext from previous steps:\n{context}" if context else ""
        prompt = f"Execute the following task step:{ctx_section}\n\nSTEP: {step}"

        result = await self.think(prompt, system=self._get_system_prompt())
        logger.info("[ExecutorAgent] Step complete: %.80s…", result.replace('\n', ' '))
        return result

    def _get_system_prompt(self) -> str:
        return EXECUTOR_SYSTEM
