"""
backend/core/responses.py
Standard response envelope + list helper.
"""
from typing import Any, List


def success_response(data: Any = None) -> dict:
    """Wrap single-item or dict data."""
    return {"success": True, "data": data if data is not None else {}, "error": None}


def list_response(items: List[Any]) -> dict:
    """Wrap list data — keeps items directly in data as array."""
    return {"success": True, "data": items, "error": None}


def error_response(error_msg: str) -> dict:
    return {"success": False, "data": {}, "error": error_msg}
