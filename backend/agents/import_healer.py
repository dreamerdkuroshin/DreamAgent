"""
backend/agents/import_healer.py

Safe Import Healer — Suggest & Log, Never Hot-Patch.

Philosophy:
  - Detects common NameError / ImportError patterns in the pipeline
  - Logs the problem and a concrete fix suggestion at ERROR level
  - Returns the suggestion string so caller can surface it to the user
  - Does NOT exec(), does NOT modify frame globals, does NOT retry broken code
  - Preserves full tracebacks for debugging

Usage:
    from backend.agents.import_healer import diagnose, format_error_event

    try:
        result = await some_pipeline_step()
    except NameError as e:
        suggestion = diagnose(e)
        publish(format_error_event(e, suggestion))
        raise  # Always re-raise — let the caller decide what to do
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Map of symbol names → the correct import statement
# Only stdlib and well-known project-level symbols
KNOWN_IMPORTS: dict[str, str] = {
    # stdlib
    "json":      "import json",
    "os":        "import os",
    "re":        "import re",
    "time":      "import time",
    "asyncio":   "import asyncio",
    "uuid":      "import uuid",
    "hashlib":   "import hashlib",
    "math":      "import math",
    "random":    "import random",
    "sys":       "import sys",
    "logging":   "import logging",
    "datetime":  "from datetime import datetime",
    "timedelta": "from datetime import timedelta",
    "Path":      "from pathlib import Path",
    "List":      "from typing import List",
    "Dict":      "from typing import Dict",
    "Optional":  "from typing import Optional",
    "Any":       "from typing import Any",
    "Callable":  "from typing import Callable",
    # project modules (common ones that get missed)
    "SessionLocal":     "from backend.core.database import SessionLocal",
    "redis_conn":       "from backend.core.task_queue import redis_conn",
    "memory_engine":    "from backend.core.memory_engine import memory_engine",
    "vector_db":        "from backend.memory.vector_db import vector_db",
}


def diagnose(exc: Exception) -> Optional[str]:
    """
    Inspects a NameError or ImportError and returns a concrete fix suggestion.

    Returns the suggestion string if a known fix exists, None otherwise.
    Always logs at ERROR level — failure is never silent.

    Does NOT modify any runtime state. Safe to call from anywhere.
    """
    exc_str = str(exc)

    # NameError: name 'json' is not defined
    # ImportError: cannot import name 'X' from 'Y'
    for symbol, fix in KNOWN_IMPORTS.items():
        # Match quoted symbol in the error message (both single and double quotes)
        if f"'{symbol}'" in exc_str or f'"{symbol}"' in exc_str:
            logger.error(
                "[ImportHealer] %s: %s\n"
                "           └── Suggested fix: add '%s' to the module imports.\n"
                "           └── This is a CODE BUG — the module is missing a top-level import.",
                type(exc).__name__, exc_str, fix
            )
            return fix

    # Unknown symbol — log but don't guess
    logger.error(
        "[ImportHealer] %s: %s\n"
        "           └── No known fix suggestion available. Full traceback follows.",
        type(exc).__name__, exc_str
    )
    return None


def format_error_event(exc: Exception, suggestion: Optional[str] = None) -> dict:
    """
    Formats a structured error event for the SSE publish() pipeline.
    Includes the fix suggestion if available.

    Example output:
        {
            "type": "error",
            "agent": "import_healer",
            "content": "⚠️ Internal error: name 'json' is not defined.\nSuggested fix: import json",
            "recoverable": false
        }
    """
    base_msg = f"⚠️ Internal error: {exc}"
    if suggestion:
        base_msg += f"\n💡 Developer fix: `{suggestion}`"

    return {
        "type": "error",
        "agent": "import_healer",
        "content": base_msg,
        "recoverable": False,
    }
