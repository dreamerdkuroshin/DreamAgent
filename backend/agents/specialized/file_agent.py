"""
backend/agents/specialized/file_agent.py

FileAgent — Reads and analyzes local files, answers questions about content.
Sandboxed to the project root directory for security.
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Optional
from backend.llm.universal_provider import UniversalProvider

logger = logging.getLogger(__name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".yaml", ".yml", ".env", ".toml", ".html", ".css",
    ".pdf", ".xml", ".ini", ".log", ".java", ".c", ".cpp", ".cs", ".go", ".rs", ".php", ".rb", ".swift", ".kt",
    ".scss", ".less", ".sql", ".db", ".sqlite", ".sh", ".bat", ".ps1", ".gitignore", ".dockerfile",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".mp3", ".wav", ".mp4", ".mkv", ".avi",
    ".zip", ".rar", ".tar", ".gz", ".7z"
}

# Sandbox root — only files within this dir can be read
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()

MAX_FILE_BYTES = 200_000  # ~200KB max read


def _safe_read(file_path: str) -> tuple[Optional[str], Optional[str]]:
    """
    Safely read a file. Returns (content, error_message).
    Sandboxed to project root.
    """
    try:
        # Resolve to absolute path
        if not os.path.isabs(file_path):
            resolved = (_PROJECT_ROOT / file_path).resolve()
        else:
            resolved = Path(file_path).resolve()

        # Sandbox check — must be inside project root
        if not str(resolved).startswith(str(_PROJECT_ROOT)):
            return None, f"Access denied: file is outside project directory."

        if not resolved.exists():
            return None, f"File not found: {file_path}"

        name_lower = resolved.name.lower()
        if resolved.suffix.lower() not in ALLOWED_EXTENSIONS and name_lower not in ALLOWED_EXTENSIONS and name_lower != "makefile":
            return None, f"File type '{resolved.suffix}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

        size = resolved.stat().st_size
        if size > MAX_FILE_BYTES:
            return None, f"File too large ({size} bytes). Max: {MAX_FILE_BYTES} bytes."

        content = resolved.read_text(encoding="utf-8", errors="replace")
        return content, None

    except Exception as e:
        return None, f"Error reading file: {e}"


def _parse_file_query(query: str) -> tuple[Optional[str], str]:
    """
    Extract file path and question from a natural language query.
    Returns (file_path, question).
    """
    import re
    # Look for common patterns: "read X", "open X", "analyze X", "read X and ..."
    patterns = [
        r'(?:read|open|analyze|explain|summarize|show|look at)\s+["\']?([^\s"\']+\.[a-zA-Z]+)["\']?',
        r'["\']([^\s"\']+\.[a-zA-Z]+)["\']',
        r'([a-zA-Z0-9_\-/\.]+\.[a-zA-Z]+)',
    ]
    for pattern in patterns:
        m = re.search(pattern, query, re.IGNORECASE)
        if m:
            file_path = m.group(1)
            question = query  # Use full query as the question
            return file_path, question

    return None, query


class FileAgent:
    """
    Reads local files and answers questions about their content.
    """

    def __init__(self, provider: str = "auto", model: str = ""):
        self.llm = UniversalProvider(provider=provider, model=model)

    async def read_and_answer(self, query: str) -> str:
        """Parse file path from query, read it, and answer the question."""
        file_path, question = _parse_file_query(query)

        if not file_path:
            return "Please specify a file path to read. Example: 'read main.py and explain what it does'"

        content, error = _safe_read(file_path)
        if error:
            return f"❌ {error}"

        logger.info(f"[FileAgent] Read {file_path} ({len(content)} chars)")

        q_lower = query.lower()
        if "show" in q_lower or "print content" in q_lower:
            return f"📄 **{file_path}**\n\n```\n{content[:10000]}\n```"

        prompt = (
            f"File: {file_path}\n\n"
            f"Content:\n```\n{content}\n```\n\n"
            f"User question: {question}\n\n"
            "Provide a clear, helpful answer about this file's content."
        )

        try:
            answer = await asyncio.wait_for(self.llm.complete(prompt), timeout=30)
            return f"📄 **{file_path}**\n\n{str(answer).strip()}"
        except Exception as e:
            logger.warning(f"[FileAgent] LLM failed: {e}")
            # Return raw content truncated
            return f"📄 **{file_path}**\n\n```\n{content[:2000]}\n```"


# Handler for StructuredRouter
async def _file_handler(query: str) -> str:
    agent = FileAgent()
    return await agent.read_and_answer(query)


def register(router=None):
    """Register this agent with a StructuredRouter instance."""
    if router:
        router.register_tool("read_file", _file_handler)
    else:
        from backend.agents.structured_router import register_tool
        register_tool("read_file", _file_handler)
