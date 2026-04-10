import os
import requests
import time
from urllib.parse import urlencode
from dotenv import load_dotenv
from db.db import get_api_key, get_oauth_token, save_oauth_token

load_dotenv()

CLIENT_ID     = os.getenv("MICROSOFT_CLIENT_ID")
CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
TENANT_ID     = os.getenv("MICROSOFT_TENANT_ID", "common")
REDIRECT_URI  = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/api/oauth/microsoft/callback")

AUTH_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize"
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

SCOPES = ["User.Read", "Files.Read", "Files.ReadWrite", "Team.ReadBasic.All", "offline_access"]

def get_auth_url():
    """Build the authorization URL for Microsoft OAuth."""
    client_id = get_api_key("microsoft_client_id") or os.getenv("MICROSOFT_CLIENT_ID")
    redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/api/oauth/microsoft/callback")

    if not client_id:
        return None

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": " ".join(SCOPES)
    }
    return f"{AUTH_URL}?{urlencode(params)}"

def get_token(code):
    """Exchange the authorization code for an access token."""
    client_id     = get_api_key("microsoft_client_id")     or os.getenv("MICROSOFT_CLIENT_ID")
    client_secret = get_api_key("microsoft_client_secret") or os.getenv("MICROSOFT_CLIENT_SECRET")
    redirect_uri  = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/api/oauth/microsoft/callback")

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    r = requests.post(TOKEN_URL, data=data)
    return r.json()

def refresh_access_token(refresh_token_value):
    """Refresh the access token using the refresh token."""
    client_id     = get_api_key("microsoft_client_id")     or os.getenv("MICROSOFT_CLIENT_ID")
    client_secret = get_api_key("microsoft_client_secret") or os.getenv("MICROSOFT_CLIENT_SECRET")

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token_value,
        "grant_type": "refresh_token"
    }
    r = requests.post(TOKEN_URL, data=data)
    return r.json()

def get_valid_token():
    """Call this before every Microsoft API task. Returns access token or None."""
    token_data = get_oauth_token("microsoft")
    if not token_data:
        return None

    # Check if expired (Microsoft tokens last ~1 hour)
    expires_at = token_data.get("expires_at", 0)
    if time.time() > expires_at - 60:
        # Silently refresh
        new_data = refresh_access_token(token_data["refresh_token"])
        if "access_token" in new_data:
            new_data["expires_at"] = time.time() + new_data.get("expires_in", 3600)
            # Preserve original refresh token if not returned
            if "refresh_token" not in new_data:
                new_data["refresh_token"] = token_data["refresh_token"]
            save_oauth_token("microsoft", new_data)
            return new_data["access_token"]
        return None

    return token_data["access_token"]