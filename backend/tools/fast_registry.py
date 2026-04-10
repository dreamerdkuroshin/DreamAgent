"""
backend/tools/fast_registry.py

Strict, parallel-friendly tool registry meant for fast orchestration execution.
Limits tool logic abstraction in favor of explicit asynchronous calling patterns.
"""
import asyncio
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class Tool:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def run(self, input_data: Any) -> Dict[str, Any]:
        """Override to implement tool logic."""
        return {"tool": self.name, "success": True, "data": {}, "error": None}

    def format_output(self, success: bool, data: Any, error: str = None) -> Dict[str, Any]:
        return {"tool": self.name, "success": success, "data": data, "error": error}


class SearchTool(Tool):
    def __init__(self):
        super().__init__("search", "Perform a web search.")
        
    async def run(self, input_data: Any) -> Dict[str, Any]:
        # Implementation stub
        await asyncio.sleep(0.5) # Simulate search IO
        return self.format_output(True, {"results": [f"Search result for {input_data}"]})


class WeatherTool(Tool):
    def __init__(self):
        super().__init__("weather", "Get local weather information.")

    async def run(self, input_data: Any) -> Dict[str, Any]:
        # Implementation stub
        await asyncio.sleep(0.2)
        return self.format_output(True, {"temp": "72F", "condition": "Sunny"})


class FastToolRegistry:
    def __init__(self):
        self._tools = {
            "search": SearchTool(),
            "weather": WeatherTool(),
        }

    def get_tool(self, name: str) -> Tool:
        return self._tools.get(name)

    async def run_parallel(self, tool_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Runs multiple tools concurrently.
        tool_requests: list of dicts like {"tool": "search", "input": "query"}
        """
        coroutines = []
        for req in tool_requests:
            tool_name = req.get("tool")
            input_data = req.get("input")
            tool_instance = self.get_tool(tool_name)
            
            if tool_instance:
                coroutines.append(tool_instance.run(input_data))
            else:
                # Mock a failed output for unknown tool
                logger.warning(f"Tool {tool_name} requested but not found in registry.")
                async def failed_tool():
                    return {"tool": tool_name, "success": False, "data": {}, "error": "Tool not found"}
                coroutines.append(failed_tool())
                
        return await asyncio.gather(*coroutines, return_exceptions=True)

# Global registry instance
fast_tools = FastToolRegistry()
