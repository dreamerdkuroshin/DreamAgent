from backend.tools.search import SearchTool
from backend.tools.code import CodeTool
from backend.tools.news import NewsAnalystTool
from backend.core.tool_tracker import tool_tracker
import time
import functools

# Dynamically loaded plugins
try:
    from plugins.loader import PLUGINS
except ImportError:
    PLUGINS = {}

class TrackedTool:
    def __init__(self, name: str, tool_instance):
        self.name = name
        self._tool = tool_instance
        
    def run(self, *args, **kwargs):
        start = time.time()
        success = True
        try:
            result = self._tool.run(*args, **kwargs)
            # If the tool failed gracefully by returning an error string
            if isinstance(result, str) and ("Error:" in result[:20] or "unavailable" in result.lower()):
                success = False
            return result
        except Exception as e:
            success = False
            raise e
        finally:
            latency = int((time.time() - start) * 1000)
            tool_tracker.record_call(self.name, success, latency)

_RAW_TOOLS = {
    "search": SearchTool(),
    "code": CodeTool(),
    "news": NewsAnalystTool(),
}

# Inject auto-discovered plugins
for name, instance in PLUGINS.items():
    _RAW_TOOLS[name] = instance

TOOLS = {name: TrackedTool(name, instance) for name, instance in _RAW_TOOLS.items()}
ALLOWED_TOOLS = list(TOOLS.keys())
