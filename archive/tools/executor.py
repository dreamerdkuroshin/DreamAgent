import logging
import asyncio
from typing import Any

logger = logging.getLogger(__name__)

class ToolExecutor:
    """Entry point to Safe Sandbox and generic tools."""
    def __init__(self):
        # We can dynamically inject sandbox or registry here if needed
        pass

    async def execute(self, action: dict) -> Any:
        tool_name = action.get("tool")
        input_data = action.get("input")

        if tool_name == "search":
            return f"Mock search result for {input_data}"
        elif tool_name == "code":
            return await self.run_code(input_data)
        elif tool_name == "none":
            return f"Thought finished: {input_data}"
            
        return f"Unknown tool requested: {tool_name}"

    async def run_code(self, code: str) -> str:
        # In the next step we will wire this to a Docker/Subprocess Sandbox.
        logger.info(f"Executing code safely: {code[:50]}...")
        from sandbox.sandbox import Sandbox
        sandbox = Sandbox()
        return await sandbox.run(code)
