"""
backend/agents/fixer.py

FixerAgent — analyzes code and tests to fix any bugs or linting issues.
"""
import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

FIXER_SYSTEM = """You are an expert Fixer Agent.
You will be provided with the original implementation code and the expected tests.
Your job is to identify any bugs, syntax errors, or logical flaws in the implementation.
If there are issues, output the FIXED implementation code in a markdown block.
If the code is already perfect and passes the logic described by the tests, reply with EXACTLY: "NO_FIX_NEEDED"
"""

class FixerAgent(BaseAgent):
    def __init__(self, llm, tools=None):
        super().__init__(llm, memory=None, tools=tools, role="fixer")

    async def fix(self, code: str, tests: str) -> str:
        prompt = f"IMPLEMENTATION CODE:\n{code}\n\nTEST CODE:\n{tests}\n\nPlease fix any issues in the implementation code, or reply NO_FIX_NEEDED."
        logger.info("[FixerAgent] Checking for issues to fix...")
        return await self.think(prompt, system=FIXER_SYSTEM)
