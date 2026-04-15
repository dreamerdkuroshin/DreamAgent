"""
backend/oauth/providers/base.py

Abstract base class all OAuth providers must implement.
Each provider is a self-contained unit with zero shared state.
"""
from abc import ABC, abstractmethod
from fastapi import Request
from typing import Dict, Any


class OAuthException(Exception):
    """
    Structured OAuth error that carries provider context.
    Allows the router to return clean, actionable error responses
    instead of generic 500s.
    """
    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")


class BaseOAuthProvider(ABC):
    """Universal interface for all OAuth providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier e.g. 'google', 'slack'"""

    @abstractmethod
    def get_auth_url(self, state: str) -> str:
        """Build the provider's authorization URL including all required scopes."""

    @abstractmethod
    async def handle_callback(self, request: Request) -> Dict[str, Any]:
        """
        Exchange the authorization code for tokens.
        Must return a dict with keys:
            access_token, refresh_token (if available), expires_at, raw (full response)
        Raises OAuthException on any failure.
        """

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Use the refresh_token to get a new access_token."""
