from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from backend.core.database import get_session
from backend.services import auth_service
from backend.core.responses import success_response, error_response

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.get("/status")
def get_status(service: str, db: Session = Depends(get_session)):
    if service == "telegram":
        token = auth_service.get_api_key(db, "telegram")
        return success_response({"status": "connected" if token else "not_connected", "token_configured": bool(token)})
    
    token_json = auth_service.get_oauth_token(db, service)
    if not token_json:
        return error_response(f"{service.capitalize()} not connected.")
    return success_response({"status": "connected", "service": service})

@router.post("/keys")
def save_key(data: dict, db: Session = Depends(get_session)):
    service = data.get("service")
    key = data.get("key")
    if not service or not key:
        raise HTTPException(status_code=400, detail="service and key are required")
    # TODO(Security): API keys are currently stored in plaintext. Implement AES encryption or secure hashing in V3.
    auth_service.save_api_key(db, service, key)
    return success_response({"status": "saved", "service": service})
