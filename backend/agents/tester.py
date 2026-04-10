"""
backend/agents/tester.py

TesterAgent — generates unit tests and verification steps for the written code.
"""
import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

TESTER_SYSTEM = """You are an expert Tester Agent.
Given the implementation code written by a Coder, your job is to write a comprehensive suite of tests.
Focus on edge cases, boundary conditions, and typical usage.
Output the test code in proper markdown blocks.
Explain briefly how to run the tests.
"""

class TesterAgent(BaseAgent):
    def __init__(self, llm, tools=None):
        super().__init__(llm, memory=None, tools=tools, role="tester")

    async def test(self, code_implementation: str, task: str) -> str:
        prompt = f"ORIGINAL TASK:\n{task}\n\nIMPLEMENTATION CODE:\n{code_implementation}\n\nPlease write tests to verify this implementation."
        logger.info("[TesterAgent] Generating tests...")
        return await self.think(prompt, system=TESTER_SYSTEM)
