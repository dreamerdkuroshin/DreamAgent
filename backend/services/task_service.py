from sqlalchemy.orm import Session
from backend.core import models

def get_tasks(db: Session, agent_id: str = None, status: str = None):
    query = db.query(models.Task)
    if agent_id:
        query = query.filter(models.Task.agent_id == agent_id)
    if status:
        query = query.filter(models.Task.status == status)
    return query.order_by(models.Task.created_at.desc()).all()

def create_task(db: Session, task_data: dict):
    try:
        task = models.Task(
            agent_id=task_data.get("agent_id"),
            title=task_data.get("title"),
            description=task_data.get("description"),
            status=task_data.get("status", "pending"),
            priority=task_data.get("priority", "medium")
        )
        db.add(task)

        # Fix #10: safe null check on task_count
        agent = db.query(models.Agent).filter(models.Agent.id == task.agent_id).first()
        if agent:
            agent.task_count = (agent.task_count or 0) + 1

        db.commit()
        db.refresh(task)
        return task
    except Exception as e:
        db.rollback()
        raise e

def update_task(db: Session, task_id: int, task_data: dict):
    try:
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if not task:
            return False
        for key, value in task_data.items():
            if hasattr(task, key) and key != "id":
                setattr(task, key, value)
        db.commit()
        db.refresh(task)
        return True
    except Exception as e:
        db.rollback()
        raise e
