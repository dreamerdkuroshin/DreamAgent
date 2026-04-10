"""
connectors/local/filesystem.py
FileSystem tool with path traversal protection.

All file access is restricted to an allowed root directory.
Attempts to read or write outside that root (including via ../ traversal,
symlinks, or absolute paths) raise PermissionError.

Configure the allowed root with the FILESYSTEM_ROOT environment variable.
Defaults to the current working directory.
"""

import os
import logging

logger = logging.getLogger(__name__)


def _get_allowed_root() -> str:
    root = os.getenv("FILESYSTEM_ROOT", os.getcwd())
    return os.path.realpath(root)


def _safe_path(path: str) -> str:
    """
    Resolve path and verify it sits inside the allowed root.

    Raises PermissionError if the resolved path escapes the root.
    Returns the resolved absolute path on success.
    """
    allowed_root = _get_allowed_root()
    # Resolve symlinks and normalise separators.
    resolved = os.path.realpath(os.path.join(allowed_root, path))

    # Ensure the resolved path starts with the root + a separator,
    # preventing root == "/tmp" from allowing "/tmp-evil/file".
    if not (resolved == allowed_root or resolved.startswith(allowed_root + os.sep)):
        raise PermissionError(
            f"Access denied: '{path}' resolves to '{resolved}', "
            f"which is outside the allowed root '{allowed_root}'."
        )
    return resolved


class FileSystemTool:
    """File I/O confined to an allowed root directory."""

    def read_file(self, path: str) -> str:
        safe = _safe_path(path)
        logger.debug("FileSystemTool.read_file: %s", safe)
        with open(safe, "r", encoding="utf-8") as f:
            return f.read()

    def write_file(self, path: str, content: str) -> str:
        safe = _safe_path(path)
        # Ensure parent directory exists (within root).
        os.makedirs(os.path.dirname(safe) or ".", exist_ok=True)
        logger.debug("FileSystemTool.write_file: %s", safe)
        with open(safe, "w", encoding="utf-8") as f:
            f.write(content)
        return "file written"

    def list_dir(self, path: str = ".") -> list[str]:
        safe = _safe_path(path)
        return os.listdir(safe)

    def delete_file(self, path: str) -> str:
        safe = _safe_path(path)
        os.remove(safe)
        return "file deleted"
