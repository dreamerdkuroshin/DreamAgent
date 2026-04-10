"""
tools/tool_intelligence.py (v10)

Auto-picks best tool/agent from message content.
Used by the UltraAgent router to select the right specialized execution module.
"""

class ToolIntelligence:
    def __init__(self):
        self.CODE_KEYWORDS = {
            "code", "function", "class", "script", "program", "debug", "refactor",
            "implement", "algorithm", "python", "typescript", "java", "sql",
            "api", "endpoint", "write a", "create a"
        }
        self.JS_KEYWORDS = {
            "javascript", "js", "node.js", "nodejs", "npm", "node"
        }
        self.SEARCH_KEYWORDS = {
            "search", "research", "find", "look up", "explain", "what is", "who is",
            "history", "compare", "summarize", "overview", "describe", "tell me about"
        }
        self.MATH_KEYWORDS = {
            "calculate", "compute", "solve", "integral", "derivative", "matrix",
            "probability", "statistics", "equation", "formula", "math", "square root",
            "percentage", "average", "mean", "median", "prime", "factorial"
        }
        self.SHELL_KEYWORDS = {
            "run", "execute", "terminal", "shell", "command", "install", "pip install",
            "npm install", "bash", "cmd", "powershell", "ls", "dir", "mkdir", "cd",
            "python ", "node ", "git ", "chmod", "ping", "ifconfig", "ipconfig",
            "check", "restart", "kill"
        }
        self.INTEGRATION_KEYWORDS = {
            "telegram token", "discord token", "whatsapp token", "slack token",
            "start bot", "my telegram bot", "here is my token", "bot token",
            "run telegram", "run whatsapp", "run discord"
        }

    def choose_tool(self, message: str) -> str:
        """Analyze message content and return the optimal tool/agent role string."""
        lower = message.lower()
        
        # Exact arithmetic checks
        if any(char.isdigit() for char in lower):
            if "+" in lower or "-" in lower or "*" in lower or "/" in lower:
                # Unless it looks like a path/command, treat simple arithmetic as math
                if not any(kw in lower for kw in ["/", "cd ", "mkdir "]):
                    return "math"

        # Check integrations first (highly specific)
        if any(kw in lower for kw in self.INTEGRATION_KEYWORDS):
            return "integration"
            
        # JS vs Code vs Shell precedence
        if any(kw in lower for kw in self.SHELL_KEYWORDS):
            if any(kw in lower for kw in self.CODE_KEYWORDS) or any(kw in lower for kw in self.JS_KEYWORDS):
                # Distinguish JS Code vs Generic Code
                if any(kw in lower for kw in self.JS_KEYWORDS):
                    return "js"
                return "code"
            return "shell"
            
        if any(kw in lower for kw in self.JS_KEYWORDS):
            return "js"
            
        if any(kw in lower for kw in self.CODE_KEYWORDS):
            return "code"
            
        if any(kw in lower for kw in self.MATH_KEYWORDS):
            return "math"
            
        if any(kw in lower for kw in self.SEARCH_KEYWORDS):
            return "search"
            
        return "default"