"""
backend/oauth/providers/google.py

Google OAuth 2.0 — Gmail, Drive, Calendar, YouTube
Uses offline access_type + include_granted_scopes for incremental authorization.
Correctly handles the one-time refresh_token delivery from Google.
"""
import os
import time
import httpx
from urllib.parse import urlencode
from fastapi import Request
from typing import Dict, Any
from .base import BaseOAuthProvider, OAuthException

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/youtube.readonly",
    "openid", "email", "profile"
]


class GoogleOAuth(BaseOAuthProvider):
    name = "google"

    @property
    def client_id(self):
        return os.getenv("GOOGLE_CLIENT_ID", "")

    @property
    def client_secret(self):
        return os.getenv("GOOGLE_CLIENT_SECRET", "")

    @property
    def redirect_uri(self):
        return os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8001/api/v1/oauth/google/callback")

    def __init__(self):
        pass

    def get_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",            # Required for refresh token
            "prompt": "consent",                 # Force re-consent so refresh_token is always returned
            "include_granted_scopes": "true",    # ✅ Incremental auth: accumulate previously granted scopes
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def handle_callback(self, request: Request) -> Dict[str, Any]:
        code = request.query_params.get("code")
        if not code:
            raise OAuthException("google", "Missing authorization code")

        async with httpx.AsyncClient() as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            })

        if resp.status_code != 200:
            raise OAuthException("google", f"HTTP error {resp.status_code}: {resp.text}")

        data = resp.json()
        if "error" in data:
            raise OAuthException("google", data.get("error_description", data.get("error")))

        # ✅ Capture scope from Google's response (populated when include_granted_scopes=true)
        scope = data.get("scope", " ".join(SCOPES))

        return {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),   # May be None on re-auth — manager handles fallback
            "expires_at": int(time.time()) + data.get("expires_in", 3600),
            "scope": scope,
            "raw": data,
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            })
        data = resp.json()
        return {
            "access_token": data.get("access_token"),
            "expires_at": int(time.time()) + data.get("expires_in", 3600),
            # refresh_token not returned on refresh — oauth_manager retains existing
        }
