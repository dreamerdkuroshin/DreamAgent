"""
backend/tools/fast_registry.py

Strict, parallel-friendly tool registry meant for fast orchestration execution.
Includes Tavily web/news search and Ahrefs SEO tools.
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


class TavilyWebSearch(Tool):
    """Tavily-powered web search with DuckDuckGo fallback."""

    def __init__(self):
        super().__init__("search", "Search the web using Tavily AI (real-time results + AI summary).")

    async def run(self, input_data: Any) -> Dict[str, Any]:
        try:
            from backend.tools.tavily_tool import TavilySearchTool
            tool = TavilySearchTool()
            result = await asyncio.to_thread(tool.run, str(input_data))
            return self.format_output(True, {"result": result})
        except Exception as e:
            return self.format_output(False, {}, str(e))


class TavilyNewsSearch(Tool):
    """Tavily news search for latest events and breaking news."""

    def __init__(self):
        super().__init__("news_search", "Search latest news using Tavily News API.")

    async def run(self, input_data: Any) -> Dict[str, Any]:
        try:
            from backend.tools.tavily_tool import TavilyNewsTool
            tool = TavilyNewsTool()
            result = await asyncio.to_thread(tool.run, str(input_data))
            return self.format_output(True, {"result": result})
        except Exception as e:
            return self.format_output(False, {}, str(e))


class AhrefsSEOSearch(Tool):
    """Ahrefs SEO analysis tool for domain metrics and keyword research."""

    def __init__(self):
        super().__init__("seo_analysis", "Analyse a domain or keyword with Ahrefs SEO data.")

    async def run(self, input_data: Any) -> Dict[str, Any]:
        try:
            from backend.tools.tavily_tool import AhrefsSEOTool
            tool = AhrefsSEOTool()
            result = await asyncio.to_thread(tool.run, str(input_data))
            return self.format_output(True, {"result": result})
        except Exception as e:
            return self.format_output(False, {}, str(e))


class WeatherTool(Tool):
    def __init__(self):
        super().__init__("weather", "Get local weather information.")

    async def run(self, input_data: Any) -> Dict[str, Any]:
        await asyncio.sleep(0.2)
        return self.format_output(True, {"temp": "72F", "condition": "Sunny"})


class FastToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {
            "search":       TavilyWebSearch(),
            "news_search":  TavilyNewsSearch(),
            "seo_analysis": AhrefsSEOSearch(),
            "weather":      WeatherTool(),
        }

    def get_tool(self, name: str) -> Tool:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

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
                logger.warning(f"Tool {tool_name} requested but not found in registry.")
                async def failed_tool():
                    return {"tool": tool_name, "success": False, "data": {}, "error": "Tool not found"}
                coroutines.append(failed_tool())

        return await asyncio.gather(*coroutines, return_exceptions=True)


# Global registry instance
fast_tools = FastToolRegistry()
