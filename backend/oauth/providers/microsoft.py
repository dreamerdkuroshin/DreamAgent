"""
backend/oauth/providers/microsoft.py

Microsoft OAuth 2.0 — Teams, Excel, Word, OneDrive, Mail
Uses Microsoft Graph API with multi-tenant support.
"""
import os
import time
import httpx
from fastapi import Request
from typing import Dict, Any
from urllib.parse import urlencode
from .base import BaseOAuthProvider, OAuthException

MS_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

SCOPES = [
    "openid", "profile", "email", "offline_access",
    "User.Read",
    "Files.ReadWrite.All",
    "Mail.ReadWrite",
    "Calendars.ReadWrite",
    "Chat.ReadWrite",
]


class MicrosoftOAuth(BaseOAuthProvider):
    name = "microsoft"

    @property
    def client_id(self):
        return os.getenv("MICROSOFT_CLIENT_ID", "")

    @property
    def client_secret(self):
        return os.getenv("MICROSOFT_CLIENT_SECRET", "")

    @property
    def redirect_uri(self):
        return os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8001/api/v1/oauth/microsoft/callback")

    def __init__(self):
        pass

    def get_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "response_mode": "query",
            "state": state,
        }
        return f"{MS_AUTH_URL}?{urlencode(params)}"
    async def handle_callback(self, request: Request) -> Dict[str, Any]:
        code = request.query_params.get("code")
        if not code:
            raise OAuthException("microsoft", "Missing authorization code")

        async with httpx.AsyncClient() as client:
            resp = await client.post(MS_TOKEN_URL, data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
                "scope": " ".join(SCOPES),
            })

        if resp.status_code != 200:
            raise OAuthException("microsoft", f"HTTP error {resp.status_code}: {resp.text}")

        data = resp.json()
        if "error" in data:
            raise OAuthException("microsoft", data.get("error_description", data.get("error")))

        return {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "expires_at": int(time.time()) + data.get("expires_in", 3600),
            "raw": data,
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(MS_TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(SCOPES),
            })
        data = resp.json()
        return {
            "access_token": data.get("access_token"),
            "expires_at": int(time.time()) + data.get("expires_in", 3600),
        }
