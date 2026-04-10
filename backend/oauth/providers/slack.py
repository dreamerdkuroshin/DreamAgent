"""
backend/oauth/providers/slack.py

Slack OAuth 2.0 — workspace bots, channel messaging, user info.
Slack uses a bot_token separate from user_token. We store both.
"""
import os
import time
import httpx
from fastapi import Request
from typing import Dict, Any
from .base import BaseOAuthProvider

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

    def __init__(self):
        self.client_id = os.getenv("SLACK_CLIENT_ID", "")
        self.client_secret = os.getenv("SLACK_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv("SLACK_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/slack/callback")

    def get_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(SCOPES),
            "user_scope": ",".join(USER_SCOPES),
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{SLACK_AUTH_URL}?{query}"

    async def handle_callback(self, request: Request) -> Dict[str, Any]:
        code = request.query_params.get("code")
        async with httpx.AsyncClient() as client:
            resp = await client.post(SLACK_TOKEN_URL, data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            })
        data = resp.json()
        # Slack returns both bot token and user token
        bot_token = data.get("access_token")
        user_token = data.get("authed_user", {}).get("access_token", "")
        return {
            "access_token": bot_token,
            "refresh_token": user_token,  # Store user token in refresh_token field
            "expires_at": int(time.time()) + (365 * 24 * 3600),  # Slack tokens are long-lived
            "raw": data,
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        # Slack does not have token refresh — tokens are long-lived
        return {"access_token": refresh_token, "expires_at": int(time.time()) + (365 * 24 * 3600)}
