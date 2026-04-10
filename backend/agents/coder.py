"""
backend/agents/coder.py

CoderAgent — writes the actual implementation code based on a plan.
"""
import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

CODER_SYSTEM = """You are an expert Coder Agent.
Given a detailed task or plan, write the full, complete implementation code.
Always output the code in proper markdown blocks with the correct language tag.
Do not omit details or use placeholders like '...'.
Focus purely on implementation. Ensure the code is robust and efficient.
"""

class CoderAgent(BaseAgent):
    def __init__(self, llm, tools=None):
        super().__init__(llm, memory=None, tools=tools, role="coder")

    async def code(self, task: str, context: str = "") -> str:
        prompt = f"TASK:\n{task}\n\nCONTEXT:\n{context}\n\nPlease provide the full implementation code."
        logger.info("[CoderAgent] Generating code for task...")
        return await self.think(prompt, system=CODER_SYSTEM)
