from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.core.database import get_session
from backend.services import task_service
from backend.core.task_queue import enqueue_task
from backend.core.execution_engine import run_task_background
from backend.core.responses import success_response, list_response

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

@router.get("")
def list_tasks(agentId: str = None, status: str = None, db: Session = Depends(get_session)):
    return list_response(task_service.get_tasks(db, agent_id=agentId, status=status))

@router.post("")
def create_task(task_data: dict, db: Session = Depends(get_session)):
    if not task_data.get("agent_id") or not task_data.get("title"):
        raise HTTPException(status_code=400, detail="agent_id and title are required")
    task = task_service.create_task(db, task_data)
    enqueue_task(run_task_background, task.id)
    return success_response({"id": task.id, "status": "created", "message": "Task queued"})

@router.put("/{id}")
def update_task(id: int, task_data: dict, db: Session = Depends(get_session)):
    ok = task_service.update_task(db, id, task_data)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return success_response({"status": "updated"})
