"""
backend/agents/specialized/search_agent.py

SearchAgent — an ExecutorAgent tuned for research and information synthesis.
Focuses on factual accuracy, source citation, and comprehensive summaries.
"""
from ..executor import ExecutorAgent

SEARCH_SYSTEM = """You are an expert Research and Intelligence Agent.
Your job is to gather, synthesize, and present information clearly.
Guidelines:
- Provide factual, well-organized answers with logical structure.
- Use Markdown headings and bullet points for readability.
- State what is known with high confidence vs. uncertain.
- If specific recent data is unavailable, say so rather than guessing.
- Aim for depth: cover background, current state, key players, and implications.
- Cite knowledge domains where your answer draws from (e.g., "Based on ML literature…").
"""


class SearchAgent(ExecutorAgent):
    """Specialized executor for research and information retrieval tasks."""

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools)
        self.role = "search_agent"

    def _get_system_prompt(self) -> str:
        return SEARCH_SYSTEM
