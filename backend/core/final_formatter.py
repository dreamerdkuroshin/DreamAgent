"""
backend/core/final_formatter.py

Strict formatting schema to ensure structured output from all fast orchestrator responses.
"""
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class Response(BaseModel):
    status: str = Field(..., description="E.g., 'success', 'error', 'partial'")
    type: str = Field(..., description="'answer', 'tool', or 'error'")
    content: str = Field(..., description="The main text payload of the response")
    structured: Dict[str, Any] = Field(default_factory=dict, description="Optional extra structured JSON data")
    error: Optional[str] = Field(None, description="Detailed error information if applicable")

def format_final_response(
    status: str, 
    resp_type: str, 
    content: str, 
    structured: Optional[Dict[str, Any]] = None, 
    error: Optional[str] = None
) -> dict:
    """Helper to instantly generate the strict JSON response format."""
    obj = Response(
        status=status,
        type=resp_type,
        content=content,
        structured=structured or {},
        error=error
    )
    return obj.model_dump()
