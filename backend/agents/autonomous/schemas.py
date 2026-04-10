"""
backend/agents/autonomous/schemas.py
Pydantic data models enforcing strict structure for the auto-GPT loop.
"""
from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class TaskStep(BaseModel):
    id: int
    action: str
    tool: Optional[str] = None
    status: str = "pending" # pending, completed, failed
    result: Optional[Dict[str, Any]] = None

class TaskPlan(BaseModel):
    goal: str
    steps: List[TaskStep]
    current_step: int = 0
    completed: bool = False
