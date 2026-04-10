import pytest
import asyncio
from backend.orchestrator.intent_router import RouteDecision
from backend.orchestrator.keyword_router import KeywordRouter
from backend.orchestrator.hybrid_router import HybridRouter
from backend.orchestrator.route_cache import CachedRouter
from backend.orchestrator.task_state import TaskState, TaskContext, InvalidTransitionError
from backend.orchestrator.retry import with_retry, NON_RETRYABLE

@pytest.mark.asyncio
async def test_keyword_router():
    router = KeywordRouter()
    
    # Builder
    res = await router.route("build a website")
    assert res.intent == "builder"
    assert res.confidence >= 0.8
    
    # Continue
    res = await router.route("continue my last project")
    assert res.intent == "continue"
    assert res.confidence >= 0.8
    
    # Update (requires session_id)
    res = await router.route("add login page", context={"session_id": "123"})
    assert res.intent == "update"
    
    # Low confidence chat
    res = await router.route("what is the capital of france?")
    assert res.intent == "chat"
    assert res.confidence <= 0.5


@pytest.mark.asyncio
async def test_cache_key_respects_session():
    # Cache should be context-aware
    router = CachedRouter(KeywordRouter())
    
    res1 = await router.route("add a login page", context={"session_id": "userA"})
    res2 = await router.route("add a login page", context={"session_id": "userB"})
    
    # They should produce different cache keys because of the context
    key1 = router._make_key("add a login page", {"session_id": "userA"})
    key2 = router._make_key("add a login page", {"session_id": "userB"})
    
    assert key1 != key2


def test_task_state_transitions():
    ctx = TaskContext("task_1")
    
    assert ctx.state == TaskState.PENDING
    ctx.transition(TaskState.ROUTING)
    assert ctx.state == TaskState.ROUTING
    
    ctx.transition(TaskState.RUNNING)
    assert ctx.state == TaskState.RUNNING
    
    ctx.transition(TaskState.COMPLETED)
    assert ctx.state == TaskState.COMPLETED
    
    # Invalid transition (already completed)
    with pytest.raises(InvalidTransitionError):
        ctx.transition(TaskState.RUNNING)


@pytest.mark.asyncio
async def test_retry_stops_on_non_retryable():
    ctx = TaskContext("task_retry", max_retries=3)
    
    attempts = 0
    
    async def _fail_auth():
        nonlocal attempts
        attempts += 1
        raise PermissionError("Invalid API key")
        
    with pytest.raises(PermissionError):
        ctx.transition(TaskState.ROUTING)
        await with_retry(_fail_auth, ctx)
        
    # Should only run once, because PermissionError is in NON_RETRYABLE
    assert attempts == 1
    assert ctx.state == TaskState.FAILED
    
    
@pytest.mark.asyncio
async def test_retry_retries_transient_errors():
    ctx = TaskContext("task_retry_2", max_retries=2)
    
    attempts = 0
    
    async def _fail_transient():
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise ConnectionError("Temporarily down")
        return "success"
        
    ctx.transition(TaskState.ROUTING)
    res = await with_retry(_fail_transient, ctx)
    
    assert res == "success"
    assert attempts == 3
    assert ctx.state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_llm_router_timeout(monkeypatch):
    from backend.orchestrator.llm_router import LLMRouter
    
    # Mock the LLM call to hang forever
    async def _hang(*args, **kwargs):
        await asyncio.sleep(5.0)
        
    router = LLMRouter()
    monkeypatch.setattr(router, "_classify", _hang)
    
    # Should not take 5 seconds, should hit the 1.2s timeout
    res = await router.route("hang me")
    assert res.intent == "chat"
    assert res.metadata.get("fallback") == "timeout"
