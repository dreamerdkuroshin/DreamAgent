"""
safety/action_validator.py
Action validator with robust tool-name blocking.

Improvements over previous version:
  - Exact-match only (rm, del) extended with destructive-verb substring matching
    so aliases (remove, unlink, drop, wipe, truncate, purge) are also blocked.
  - Blocklist loaded from BLOCKED_TOOLS_PATH (JSON array) so it can be updated
    without code changes.
  - Block reason returned to the caller so it can be logged / surfaced in UI.
"""

import json
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default blocklist — exact tool names that are always rejected
# ---------------------------------------------------------------------------
_DEFAULT_EXACT_BLOCKED: set[str] = {
    "rm", "del", "delete", "remove", "unlink",
    "drop_table", "drop", "truncate", "format",
    "shutdown", "reboot", "halt", "poweroff",
    "exec", "eval", "os.system", "subprocess",
    "mkfs", "fdisk", "wipefs", "purge",
}

# Destructive verb patterns — matched against the tool name as a substring
# (case-insensitive).  Add entries here if new dangerous verbs appear.
_DESTRUCTIVE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bdelet", re.IGNORECASE),   # delete, deletion
    re.compile(r"\bremov", re.IGNORECASE),   # remove, removal
    re.compile(r"\bdrop\b", re.IGNORECASE),
    re.compile(r"\btrunc", re.IGNORECASE),   # truncate
    re.compile(r"\bpurg", re.IGNORECASE),    # purge
    re.compile(r"\bwipe\b", re.IGNORECASE),
    re.compile(r"\berase\b", re.IGNORECASE),
    re.compile(r"\bformat\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\bkill\b", re.IGNORECASE),
]


def _load_extra_blocked(path: str | None) -> set[str]:
    if not path:
        return set()
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("BLOCKED_TOOLS_PATH must contain a JSON array of strings.")
        return {str(item).lower() for item in data}
    except Exception as e:
        logger.error("ActionValidator: failed to load blocked tools from '%s': %s", path, e)
        return set()


class ActionValidator:
    """Validate proposed actions against safety policies."""

    def __init__(self):
        self._exact_blocked: set[str] = _DEFAULT_EXACT_BLOCKED | _load_extra_blocked(
            os.getenv("BLOCKED_TOOLS_PATH")
        )
        self._rules: List[Callable[[Dict[str, Any]], Tuple[bool, Optional[str]]]] = []

    def validate_action(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate an action dict before execution.

        Returns (True, None) if the action is permitted, or
        (False, reason_string) if it is blocked.
        """
        if not action:
            return False, "Action is empty or None."

        tool_name = str(
            action.get("tool", action.get("tool_name", ""))
        ).lower().strip()

        # --- Exact match ---
        if tool_name in self._exact_blocked:
            reason = f"Tool '{tool_name}' is in the blocked list."
            logger.warning("ActionValidator blocked (exact): %s", tool_name)
            return False, reason

        # --- Destructive pattern match ---
        for pattern in _DESTRUCTIVE_PATTERNS:
            if pattern.search(tool_name):
                reason = (
                    f"Tool '{tool_name}' matches a destructive-verb pattern "
                    f"({pattern.pattern}) and is blocked by default. "
                    "Add an explicit allow-rule if this tool is safe."
                )
                logger.warning("ActionValidator blocked (pattern): %s", tool_name)
                return False, reason

        # --- Custom rules ---
        for rule in self._rules:
            try:
                valid, reason = rule(action)
                if not valid:
                    logger.warning(
                        "ActionValidator rule rejected '%s': %s", tool_name, reason
                    )
                    return False, reason
            except Exception as exc:
                logger.error("ActionValidator rule raised: %s", exc)
                return False, f"Validation rule error: {exc}"

        return True, None

    def add_rule(
        self, rule: Callable[[Dict[str, Any]], Tuple[bool, Optional[str]]]
    ) -> None:
        """Register a custom validation rule."""
        self._rules.append(rule)

    def allow_tool(self, tool_name: str) -> None:
        """
        Explicitly allow a tool name that would otherwise be blocked.
        Use sparingly and only with hardcoded values — never with user input.
        """
        self._exact_blocked.discard(tool_name.lower())
        logger.info("ActionValidator: explicitly allowed tool '%s'.", tool_name)
