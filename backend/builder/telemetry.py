"""
backend/builder/telemetry.py
Local tracking for builder analytics to inform self-improvement scoring loops.
"""

from backend.core.database import SessionLocal
from backend.core.models import BuildTelemetry

def record_event(session_id: str, event_type: str, fix_attempts: int = 0):
    db = SessionLocal()
    try:
        t = BuildTelemetry(session_id=session_id, event_type=event_type, fix_attempts=fix_attempts)
        db.add(t)
        db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[Telemetry] Failed to record event: {e}")
    finally:
        db.close()

def get_stats(session_id: str) -> dict:
    db = SessionLocal()
    try:
        events = db.query(BuildTelemetry).filter(BuildTelemetry.session_id == session_id).all()
        
        counts = {
            "update_success": 0,
            "update_fail": 0,
            "rollback": 0,
            "deploy_success": 0,
            "deploy_fail": 0,
        }
        total_fix_attempts = 0
        updates_with_fixes = 0
        
        for e in events:
            if e.event_type in counts:
                counts[e.event_type] += 1
            if e.event_type == "update_success" and e.fix_attempts > 0:
                total_fix_attempts += e.fix_attempts
                updates_with_fixes += 1
                
        total_updates = counts["update_success"] + counts["update_fail"]
        total_deploys = counts["deploy_success"] + counts["deploy_fail"]
        
        success_rate = (counts["update_success"] / total_updates) if total_updates > 0 else 1.0
        deploy_success_rate = (counts["deploy_success"] / total_deploys) if total_deploys > 0 else 1.0
        avg_fix_attempts = (total_fix_attempts / updates_with_fixes) if updates_with_fixes > 0 else 0.0

        return {
            "success_rate": round(success_rate, 2),
            "avg_fix_attempts": round(avg_fix_attempts, 2),
            "deploy_success_rate": round(deploy_success_rate, 2),
            "counts": counts
        }
    finally:
        db.close()
