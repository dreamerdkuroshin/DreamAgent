"""
backend/orchestrator/__init__.py

Public API for the orchestrator module.
"""
from backend.orchestrator.intent_router import IntentRouter, RouteDecision
from backend.orchestrator.keyword_router import KeywordRouter
from backend.orchestrator.llm_router import LLMRouter
from backend.orchestrator.hybrid_router import HybridRouter
from backend.orchestrator.route_cache import CachedRouter
from backend.orchestrator.task_state import TaskState, TaskContext, InvalidTransitionError
from backend.orchestrator.retry import with_retry, get_max_retries, NON_RETRYABLE
from backend.orchestrator.observability import TaskLogger
from backend.orchestrator.execution_dispatcher import ExecutionDispatcher

__all__ = [
    # Router
    "IntentRouter", "RouteDecision",
    "KeywordRouter", "LLMRouter", "HybridRouter", "CachedRouter",
    # Task lifecycle
    "TaskState", "TaskContext", "InvalidTransitionError",
    # Retry
    "with_retry", "get_max_retries", "NON_RETRYABLE",
    # Observability
    "TaskLogger",
    # Dispatcher
    "ExecutionDispatcher",
]
