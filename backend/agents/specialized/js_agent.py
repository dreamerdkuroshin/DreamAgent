"""
backend/agents/specialized/js_agent.py

JsAgent — An agent that runs JavaScript code via Node.js.
Wraps sandbox/js_executor.py for safe sandboxed execution.
"""
import logging
from ..executor import ExecutorAgent

logger = logging.getLogger(__name__)

JS_SYSTEM = """You are a JavaScript coding expert.
When given a task, output ONLY the complete JavaScript code to accomplish it.
Do not include markdown code fences (```), explanations, or any text other than the code itself.
Make the code runnable directly via Node.js.
"""


class JsAgent(ExecutorAgent):
    """Executor that writes and runs JavaScript code."""

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools)
        self.role = "js_agent"

    async def execute(self, step: str, context: str = "") -> str:
        # 1. Ask LLM to write the JS code
        prompt = f"Task: {step}\n\nWrite JavaScript code to solve this. Output ONLY the JS code, no markdown."
        code = await self.think(prompt, system=JS_SYSTEM)
        code = str(code).strip()

        # Strip markdown fences if the LLM wrapped it
        if code.startswith("```"):
            lines = code.splitlines()
            code = "\n".join(lines[1:-1]).strip()

        logger.info("[JsAgent] Running JS code (%d chars)", len(code))

        # 2. Execute via JsExecutor
        try:
            from sandbox.js_executor import JsExecutor
            executor = JsExecutor(timeout=30)
            result = executor.execute(code)

            if result.get("success"):
                output = result.get("output", "").strip()
                return f"**JS Execution Result:**\n```\n{output}\n```\n\n[Exit code: 0]"
            else:
                err = result.get("error_output", "Unknown error")
                return f"**JS Execution Error:**\n```\n{err}\n```\n\n[Exit code: {result.get('return_code', -1)}]"

        except ImportError:
            # Node.js not installed or module missing — fall back to explanation
            logger.warning("[JsAgent] JsExecutor not available, returning code only")
            return f"**JavaScript Code:**\n```javascript\n{code}\n```\n\n⚠️ Node.js execution not available. Install Node.js to run this."
        except Exception as e:
            logger.error("[JsAgent] Error: %s", e)
            return f"**JavaScript Code:**\n```javascript\n{code}\n```\n\n[Error running: {e}]"

    def _get_system_prompt(self) -> str:
        return JS_SYSTEM
