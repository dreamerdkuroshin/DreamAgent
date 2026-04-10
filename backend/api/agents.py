from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.core.database import get_session
from backend.services import agent_service
from backend.core.responses import success_response, list_response, error_response

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

@router.delete("/all")
def delete_all_agents(confirm: bool = Query(False), db: Session = Depends(get_session)):
    if not confirm:
        raise HTTPException(status_code=400, detail="Must provide ?confirm=true to delete all agents")
    ok = agent_service.delete_all_agents(db)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete agents")
    return success_response({"status": "all_deleted"})

@router.get("")
def list_agents(db: Session = Depends(get_session)):
    return list_response(agent_service.get_agents(db))

@router.post("")
def create_agent(agent_data: dict, db: Session = Depends(get_session)):
    return success_response(agent_service.create_agent(db, agent_data))

@router.get("/{id}")
def get_agent(id: str, db: Session = Depends(get_session)):
    agent = agent_service.get_agent(db, id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return success_response(agent)

@router.put("/{id}")
def update_agent(id: str, agent_data: dict, db: Session = Depends(get_session)):
    agent = agent_service.update_agent(db, id, agent_data)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return success_response({"status": "updated", "agent": agent})

@router.delete("/{id}")
def delete_agent(id: str, db: Session = Depends(get_session)):
    ok = agent_service.delete_agent(db, id)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return success_response({"status": "deleted"})
