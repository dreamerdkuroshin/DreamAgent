"""
backend/agents/autonomous/event_adapter.py
Clean transformation mapping an Autonomous SSE `AgentEvent` dict 
into a standard linear ChatUX `publish()` payload format.
"""
from typing import Dict, Any

def to_chat_event(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "agent",
        "agent": "orchestrator", 
        "role": "system",
        "status": "running" if event["type"] not in ["final", "error"] else ("done" if event["type"] == "final" else "failed"),
        "content": f"⚙️ {event['message']}" if "tool" not in event["type"] else f"🔧 {event['message']}",
        "step_id": event.get("step_id")
    }
