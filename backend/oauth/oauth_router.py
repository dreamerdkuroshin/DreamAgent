"""
backend/oauth/oauth_router.py

Universal OAuth Routes.
Handles the secure authentication cycle for Google, Microsoft, Slack, and Notion via one simple generic entry point.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import traceback

from .oauth_manager import get_provider, save_tokens

router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])

@router.get("/{provider}/connect")
def connect(provider: str, user_id: str, bot_id: str):
    """
    Initializes the OAuth 2.0 flow for the requested external provider.
    Redirects user heavily scoped via state string encapsulation.
    """
    try:
        oauth = get_provider(provider)
        
        # We pack user_id and bot_id securely into the OAuth state 
        # so when they return in the callback, we know where to save the token!
        state = f"{user_id}::{bot_id}"
        auth_url = oauth.get_auth_url(state=state)
        
        return RedirectResponse(auth_url)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{provider}/callback")
async def callback(provider: str, request: Request):
    """
    Finalizes the OAuth 2.0 flow, extracting the single-use code + state,
    performing the token exchange, and persisting it to the encrypted Core DB vault.
    """
    state = request.query_params.get("state")
    if not state or "::" not in state:
        raise HTTPException(status_code=400, detail="Invalid callback state parameter.")

    try:
        user_id, bot_id = state.split("::", 1)
        
        oauth = get_provider(provider)
        tokens = await oauth.handle_callback(request)
        
        # Secure persistence (with AES encryption done inside manager)
        save_tokens(provider, user_id, bot_id, tokens)
        
        # Since this usually happens in a popup, tell the user they can close it
        return {
            "status": "connected", 
            "provider": provider, 
            "user_id": user_id, 
            "bot_id": bot_id,
            "message": "Authorization successful. You may close this window and return to DreamAgent."
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"OAuth Flow Failed: {e}")

@router.get("/status")
def status(provider: str, user_id: str, bot_id: str):
    from .oauth_manager import has_token
    connected = has_token(user_id, bot_id, provider)
    return {"connected": connected, "provider": provider}
