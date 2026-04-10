"""
Modes/Ultra_mode.py
Ultra mode — full planner→worker→validator pipeline.

Previous version: planner, worker, validator, and the orchestrator were all
constructed at module import time.  This means importing the file triggers
MemoryManager, model adapter, and DB initialisation — even in test
environments or when only Lite mode is used.

This version builds the pipeline lazily on first call.
"""

import logging

logger = logging.getLogger(__name__)

_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from agents.orchestrator import AgentOrchestrator
        from agents.planner_agent import PlannerAgent
        from agents.worker_agent import WorkerAgent
        from agents.agent_validator import AgentValidator
        _orchestrator = AgentOrchestrator(
            PlannerAgent(), WorkerAgent(), AgentValidator()
        )
    return _orchestrator


def run_Ultra_mode(message: str):
    """Run the full orchestrator pipeline for a message."""
    orch = _get_orchestrator()
    try:
        return orch.run_task(message)
    except Exception as exc:
        logger.error("Ultra mode failed: %s", exc)
        return f"Error: {exc}"
