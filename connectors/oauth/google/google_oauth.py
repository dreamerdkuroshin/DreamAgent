import os
import json
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv

load_dotenv()

# The scopes we need for the DreamAgent services
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "credentials.json")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/oauth/google/callback")

def get_auth_url():
    """Build the authorization URL using the official Google Flow."""
    if not os.path.exists(CREDENTIALS_FILE):
        return None
        
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    auth_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent'
    )
    return auth_url

def exchange_code(code):
    """Exchange the authorization code for tokens."""
    if not os.path.exists(CREDENTIALS_FILE):
        return {"error": "credentials.json missing"}
        
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or SCOPES)
        }
    except Exception as e:
        return {"error": str(e)}

def get_valid_credentials():
    """Call this before every API call — auto-refreshes if expired."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from db.db import get_oauth_token, save_oauth_token
    
    token_data = get_oauth_token("google")
    if not token_data:
        return None
        
    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes", SCOPES)
    )
        
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_data["access_token"] = creds.token
        save_oauth_token("google", token_data)
        
    return creds