"""
backend/agents/specialized/code_agent.py

CodeAgent — an ExecutorAgent tuned for software development tasks.
Handles code generation, debugging, refactoring, and code review.
"""
from ..executor import ExecutorAgent

CODE_SYSTEM = """You are an expert Software Engineer and Code Agent.
You write clean, production-quality code with proper error handling and comments.
When asked to write code:
- Choose the most appropriate language/framework unless specified.
- Include imports, type hints (Python), or type annotations (TS/JS).
- Add brief inline comments for non-obvious logic.
- Wrap code blocks in appropriate markdown fences (e.g. ```python).
When asked to debug: explain the bug clearly then provide the fixed code.
When asked to review: point out specific issues with line references.
"""


class CodeAgent(ExecutorAgent):
    """Specialized executor for code-related tasks."""

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools)
        self.role = "code_agent"

    def _get_system_prompt(self) -> str:
        return CODE_SYSTEM
