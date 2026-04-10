"""
backend/agents/reviewer.py

ReviewerAgent — provides the final look over the codebase to ensure quality, security, and standards.
"""
import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM = """You are an expert Senior Code Reviewer.
Your job is to review the final working implementation (and tests) produced by your team.
Check for readability, performance, security, and best practices.
If the code is ready for production, respond with a final markdown summary of the project and conclude with "APPROVED".
If minor tweaks are needed, make the tweaks and present the final ready code.
"""

class ReviewerAgent(BaseAgent):
    def __init__(self, llm, tools=None):
        super().__init__(llm, memory=None, tools=tools, role="reviewer")

    async def review(self, final_code: str, tests: str, original_task: str) -> str:
        prompt = f"TASK:\n{original_task}\n\nFINAL CODE:\n{final_code}\n\nTESTS:\n{tests}\n\nPlease perform a final review and provide the release summary."
        logger.info("[ReviewerAgent] Performing final code review...")
        return await self.think(prompt, system=REVIEWER_SYSTEM)
