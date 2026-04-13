"""
backend/agents/writer_agent.py

WriterAgent — Specialized LLM agent for creative/marketing copy and content chaining.
"""
import logging
from typing import Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

WRITER_SYSTEM = """You are a highly skilled Copywriter and Content Strategist in a multi-agent system.
Your job is to generate high-converting, engaging, and context-aware text based on instructions.

Formats you excel at:
- Brand names, taglines, and missions
- Landing page copy (UI/UX text)
- Social media content chains (e.g. video script -> thumbnail -> caption)
- Email marketing copy

Guidelines:
1. Match the requested tone exactly (e.g., "Gen Z viral", "Professional B2B").
2. Do NOT output code unless absolutely required for formatting (like markdown).
3. If chaining content (e.g. video 1, video 2), maintain thematic consistency.
4. Keep the output clean, without unnecessary conversational filler like "Here is your copy:".
"""

class WriterAgent(BaseAgent):
    """
    Specialized for creative writing, marketing copy, and content structuring.
    """

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools, role="writer")

    async def write(self, task: str, context: str = "") -> str:
        """
        Produce creative copy based on the task description and accumulated context.
        """
        logger.info("[WriterAgent] Generating copy for task: %.50s...", task)
        
        prompt = (
            f"TASK:\n{task}\n\n"
            f"CONTEXT:\n{context if context else 'No additional context provided.'}\n\n"
            f"Generate the requested copy/content. Focus purely on the output."
        )
        
        start_time = None
        import time
        start_time = time.time()
        
        result = await self.think(prompt, system=WRITER_SYSTEM)
        
        duration = time.time() - start_time
        logger.info(f"[WriterAgent] Completed in {duration:.2f}s")
        
        return result
