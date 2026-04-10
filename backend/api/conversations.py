from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.core.database import get_session
from backend.services import conversation_service
from backend.core.responses import success_response, list_response, error_response

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])

@router.delete("/all")
def delete_all_conversations(confirm: bool = Query(False), db: Session = Depends(get_session)):
    if not confirm:
        raise HTTPException(status_code=400, detail="Must provide ?confirm=true to delete all conversations")
    ok = conversation_service.delete_all_conversations(db)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete conversations")
    return success_response({"status": "all_deleted"})

@router.get("")
def get_conversations(agentId: str = None, db: Session = Depends(get_session)):
    return list_response(conversation_service.get_conversations(db, agent_id=agentId))

@router.post("")
def create_conversation(data: dict, db: Session = Depends(get_session)):
    agent_id = data.get("agentId")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agentId is required")
    title = data.get("title", "New Conversation")
    conv = conversation_service.create_conversation(db, agent_id, title)
    return success_response({"id": conv.id, "title": conv.title, "agent_id": conv.agent_id})

@router.get("/{id}/messages")
def get_messages(id: int, db: Session = Depends(get_session)):
    return list_response(conversation_service.get_messages(db, id))

@router.post("/{id}/messages")
def send_message(id: int, data: dict, db: Session = Depends(get_session)):
    role = data.get("role", "user")
    content = data.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="Content is required")
    msg = conversation_service.create_message(db, id, role, content)
    return success_response({"status": "sent", "message_id": msg.id})

@router.delete("/{id}")
def delete_conversation(id: int, db: Session = Depends(get_session)):
    ok = conversation_service.delete_conversation(db, id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return success_response({"status": "deleted"})

