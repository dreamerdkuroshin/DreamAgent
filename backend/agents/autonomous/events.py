"""
backend/agents/autonomous/events.py
Structured Pydantic schemas enforcing live SSE Event streams for the AutoGPT Loop.
"""
from pydantic import BaseModel
from typing import Optional, Any, Dict

class AgentEvent(BaseModel):
    type: str               # start, plan, step_start, tool_result, step_done, error, final
    message: str
    step_id: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
