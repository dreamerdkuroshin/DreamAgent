"""
backend/oauth/providers/slack.py

Slack OAuth 2.0 — workspace bots, channel messaging, user info.
Slack uses a bot_token separate from user_token. We store both.
"""
import os
import time
import httpx
from urllib.parse import urlencode
from fastapi import Request
from typing import Dict, Any
from .base import BaseOAuthProvider, OAuthException

SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

SCOPES = [
    "chat:write",
    "channels:read",
    "channels:history",
    "users:read",
    "files:read",
    "reactions:write",
]
USER_SCOPES = ["channels:history", "chat:write", "files:read"]


class SlackOAuth(BaseOAuthProvider):
    name = "slack"

    @property
    def client_id(self):
        return os.getenv("SLACK_CLIENT_ID", "")

    @property
    def client_secret(self):
        return os.getenv("SLACK_CLIENT_SECRET", "")

    @property
    def redirect_uri(self):
        return os.getenv("SLACK_REDIRECT_URI", "http://localhost:8001/api/v1/oauth/slack/callback")

    def __init__(self):
        pass

    def get_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(SCOPES),
            "user_scope": " ".join(USER_SCOPES),
            "state": state,
        }
        return f"{SLACK_AUTH_URL}?{urlencode(params)}"

    async def handle_callback(self, request: Request) -> Dict[str, Any]:
        code = request.query_params.get("code")
        if not code:
            raise OAuthException("slack", "Missing authorization code")

        async with httpx.AsyncClient() as client:
            resp = await client.post(SLACK_TOKEN_URL, data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            })

        if resp.status_code != 200:
            raise OAuthException("slack", f"HTTP error: {resp.text}")

        data = resp.json()

        if not data.get("ok"):
            raise OAuthException("slack", f"OAuth failed: {data.get('error')}")

        print("SLACK RESPONSE:", data)

        bot_token = data.get("access_token")
        user_token = data.get("authed_user", {}).get("access_token", "")

        return {
            "access_token": bot_token,
            "refresh_token": None,
            "expires_at": int(time.time()) + (365 * 24 * 3600),
            "scope": " ".join(SCOPES),
            "raw": {
                **data,
                "bot_token": bot_token,
                "user_token": user_token,
                "team_id": data.get("team", {}).get("id"),
                "team_name": data.get("team", {}).get("name"),
            },
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        # Slack does not have token refresh — tokens are long-lived
        return {"access_token": refresh_token, "expires_at": int(time.time()) + (365 * 24 * 3600)}
