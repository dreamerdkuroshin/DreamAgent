"""Tool permission and access control management."""

from typing import Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Permission levels for tool access."""
    DENIED = 0
    READ = 1
    WRITE = 2
    ADMIN = 3


class ToolPermission:
    """Manage permissions for tool access."""

    def __init__(self):
        """Initialize tool permission manager."""
        self.permissions: Dict[str, PermissionLevel] = {}

    def grant_permission(self, tool_name: str, level: PermissionLevel) -> None:
        """Grant permission for a tool."""
        self.permissions[tool_name] = level

    def revoke_permission(self, tool_name: str) -> None:
        """Revoke permission for a tool."""
        if tool_name in self.permissions:
            del self.permissions[tool_name]

    def has_permission(self, tool_name: str, required_level: PermissionLevel) -> bool:
        """Check if a tool has required permission level."""
        current_level = self.permissions.get(tool_name, PermissionLevel.DENIED)
        return current_level.value >= required_level.value
