"""
backend/oauth/providers/notion.py

Notion OAuth 2.0 — workspace access.
Notion tokens do not expire (long-lived), so no refresh token logic is needed.
"""
import os
import time
import httpx
from fastapi import Request
from typing import Dict, Any
from .base import BaseOAuthProvider

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"


class NotionOAuth(BaseOAuthProvider):
    name = "notion"

    def __init__(self):
        self.client_id = os.getenv("NOTION_CLIENT_ID", "")
        self.client_secret = os.getenv("NOTION_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv("NOTION_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/notion/callback")

    def get_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "owner": "user",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{NOTION_AUTH_URL}?{query}"

    async def handle_callback(self, request: Request) -> Dict[str, Any]:
        code = request.query_params.get("code")
        
        # Notion requires Basic Auth for token exchange
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                NOTION_TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                auth=(self.client_id, self.client_secret),
                headers={"Notion-Version": "2022-06-28"}
            )
        data = resp.json()
        
        # Notion returns an access_token that doesn't expire.
        return {
            "access_token": data.get("access_token"),
            "refresh_token": None,
            "expires_at": int(time.time()) + (365 * 10 * 24 * 3600), # effectively arbitrary far future
            "raw": data,
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        # Notion tokens do not expire, so this shouldn't be called.
        return {"access_token": refresh_token, "expires_at": int(time.time()) + (365 * 10 * 24 * 3600)}
