"""
monitoring/dashboard.py
Monitoring dashboard with authentication guard.

Previous version: all endpoints were publicly accessible — anyone who could
reach the port could read task counts, queue depth, and health status.
In a multi-tenant or cloud deployment this leaks operational data.

This version requires an X-Dashboard-Token header on all non-health endpoints.
Set DASHBOARD_TOKEN in your environment.  Leave it unset to disable the
dashboard entirely (returns 503 on protected routes).
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import APIKeyHeader

from monitoring.metrics import metrics

logger = logging.getLogger(__name__)

app = FastAPI(title="DreamAgent Monitoring", docs_url=None, redoc_url=None)

_TOKEN_HEADER = APIKeyHeader(name="X-Dashboard-Token", auto_error=False)
_DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")


def _require_token(token: str = Depends(_TOKEN_HEADER)):
    if not _DASHBOARD_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard is disabled (DASHBOARD_TOKEN not set).",
        )
    if token != _DASHBOARD_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dashboard token.",
        )


# ------------------------------------------------------------------
# Public
# ------------------------------------------------------------------

@app.get("/health")
def health():
    """Unauthenticated health check — safe to expose to load balancers."""
    return {"status": "ok"}


# ------------------------------------------------------------------
# Protected
# ------------------------------------------------------------------

@app.get("/metrics", dependencies=[Depends(_require_token)])
def get_metrics():
    return metrics.to_dict()


@app.get("/queue", dependencies=[Depends(_require_token)])
async def queue_status():
    try:
        from core.task_queue import task_queue
        size = task_queue.queue.qsize()
    except Exception:
        size = -1
    return {"pending_tasks": size}
