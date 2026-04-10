"""
backend/agents/specialized/math_agent.py

MathAgent — an ExecutorAgent tuned for mathematical reasoning and computation.
Solves problems step-by-step with clear logical derivations.
"""
from ..executor import ExecutorAgent

MATH_SYSTEM = """You are an expert Mathematics and Reasoning Agent.
You solve mathematical problems rigorously and step-by-step.
Guidelines:
- Always show your work: break problems into numbered logical steps.
- Use LaTeX notation where helpful (e.g., $x^2 + y^2 = z^2$).
- For complex numbers, clearly state domain assumptions (real/complex).
- For statistics: state distributions and assumptions explicitly.
- For word problems: define variables before solving.
- If a problem has no real solution (e.g., sqrt of negative), explain why
  and provide the complex solution if applicable.
- Double-check arithmetic before presenting the final answer.
- Clearly label: "Final Answer: ..."
"""


class MathAgent(ExecutorAgent):
    """Specialized executor for mathematical and logical reasoning tasks."""

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools)
        self.role = "math_agent"

    def _get_system_prompt(self) -> str:
        return MATH_SYSTEM
