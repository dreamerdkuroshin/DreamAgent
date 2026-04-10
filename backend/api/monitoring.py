"""
backend/api/monitoring.py

Frontend Monitoring endpoints.
Provides tool stats, memory stats, system health, and the /api/v1/stats
dashboard endpoint that the Monitoring page polls.
"""
from fastapi import APIRouter, Depends
from backend.core.dragonfly_manager import dragonfly
from backend.core.tool_tracker import tool_tracker
from backend.core.database import get_session
from sqlalchemy.orm import Session
from backend.core.models import Memory, Task, Message, Agent, TaskHistory, BuildSession, BuildTelemetry

router = APIRouter(tags=["monitoring"])


# ─── /v1/monitoring/* (internal namespaced routes) ───────────────────────────

@router.get("/v1/monitoring/tools")
def get_tool_stats():
    """Returns runtime stats for all tools."""
    stats = tool_tracker.get_all_stats()
    return {"success": True, "data": stats}


@router.get("/v1/monitoring/memory")
def get_memory_stats(db: Session = Depends(get_session)):
    """Returns memory subsystem stats."""
    client = dragonfly.get_client()
    session_keys = client.keys("mem:*:turns") if client else []
    session_users = len(session_keys)

    core_facts = 0
    total_facts = 0
    try:
        core_facts = db.query(Memory).filter(Memory.scope == "core").count()
        total_facts = db.query(Memory).count()
    except Exception:
        pass

    return {
        "success": True,
        "data": {
            "active_sessions": session_users,
            "core_identity_facts": core_facts,
            "total_facts": total_facts
        }
    }


@router.get("/v1/monitoring/system")
def get_system_health():
    """Aggregates system health."""
    is_dragonfly = dragonfly.is_connected()
    return {
        "success": True,
        "data": {
            "dragonfly_connected": is_dragonfly,
            "mode": "distributed" if is_dragonfly else "local"
        }
    }


# ─── /api/v1/stats — Primary Dashboard Stats ─────────────────────────────────

@router.get("/api/v1/stats")
def get_dashboard_stats(db: Session = Depends(get_session)):
    """
    Unified stats endpoint consumed by the Monitoring page.
    Returns real-time metrics from the DB and Redis task queues.
    """
    # --- Task Metrics (from DB) ---
    try:
        total_tasks = db.query(Task).count()
        completed_tasks = db.query(Task).filter(Task.status == "completed").count()
        pending_tasks = db.query(Task).filter(Task.status == "pending").count()
        failed_tasks = db.query(Task).filter(Task.status == "failed").count()
    except Exception:
        total_tasks = completed_tasks = pending_tasks = failed_tasks = 0

    # --- Agent Metrics ---
    try:
        active_agents = db.query(Agent).filter(Agent.status == "active").count()
        total_agents = db.query(Agent).count()
    except Exception:
        active_agents = total_agents = 0

    # --- Task History Metrics (for success rate) ---
    try:
        total_runs = db.query(TaskHistory).count()
        successful_runs = db.query(TaskHistory).filter(TaskHistory.success == 1).count()
        success_rate = (successful_runs / total_runs) if total_runs > 0 else 0.0
    except Exception:
        total_runs = 0
        success_rate = 0.0

    # --- Message / Token Metrics ---
    try:
        total_messages = db.query(Message).count()
    except Exception:
        total_messages = 0

    # --- Build Stats ---
    try:
        build_sessions = db.query(BuildSession).count()
        successful_builds = db.query(BuildTelemetry).filter(
            BuildTelemetry.event_type == "update_success"
        ).count()
        failed_builds = db.query(BuildTelemetry).filter(
            BuildTelemetry.event_type == "update_fail"
        ).count()
        avg_fix_attempts = 0.0
        if successful_builds + failed_builds > 0:
            from sqlalchemy import func
            avg_raw = db.query(func.avg(BuildTelemetry.fix_attempts)).scalar()
            avg_fix_attempts = round(float(avg_raw or 0), 2)
    except Exception:
        build_sessions = successful_builds = failed_builds = 0
        avg_fix_attempts = 0.0

    # --- Redis Queue Depths ---
    client = dragonfly.get_client()
    queue_simple = queue_medium = queue_complex = queue_dead = 0
    if client:
        try:
            queue_simple  = client.llen("tasks:simple")
            queue_medium  = client.llen("tasks:medium")
            queue_complex = client.llen("tasks:complex")
            queue_dead    = client.llen("tasks:dead")
        except Exception:
            pass

    return {
        # Task stats (used by Monitoring overview KPI cards)
        "totalTasks":      total_tasks,
        "completedTasks":  completed_tasks,
        "pendingTasks":    pending_tasks + queue_simple + queue_medium + queue_complex,
        "failedTasks":     failed_tasks,

        # Agent stats
        "activeAgents":    active_agents,
        "totalAgents":     total_agents,

        # Self-improvement stats (maps to 'self-improve' tab)
        "total_runs":      total_runs,
        "success_rate":    round(success_rate, 4),
        "avg_duration":    0.0,   # not yet tracked per-run

        # Messaging
        "total_messages":  total_messages,

        # Builder stats (maps to 'builder' tab)
        "build_sessions":       build_sessions,
        "successful_builds":    successful_builds,
        "failed_builds":        failed_builds,
        "avg_fix_attempts":     avg_fix_attempts,

        # Queue depths (maps to 'tasks' tab)
        "queue": {
            "simple":  queue_simple,
            "medium":  queue_medium,
            "complex": queue_complex,
            "dead":    queue_dead,
        }
    }
