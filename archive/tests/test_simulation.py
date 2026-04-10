"""
tests/test_simulation.py

Integration-style simulation tests:
- Run the agent on a list of fake tasks and assert outcomes
- Failure injection: API timeout, wrong tool output, permission denied

Run with:  pytest tests/test_simulation.py -v
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Simulation tasks ──────────────────────────────────────────────────

SIMULATION_TASKS = [
    "Summarize this document: 'AI is transforming industries.'",
    "Search the web for latest Python 3.13 features.",
    "Calculate the square root of 144.",
]


class TestSimulation:
    """
    Agent-level simulation tests using a mocked LLM.
    The loop should complete without crashing on all tasks.
    """

    def _mock_llm(self, response: str = ""):
        llm = MagicMock()
        llm.generate.return_value = (
            response or 'THINK: I will complete the task.\nACTION: {"tool": "complete", "args": {"result": "done", "confidence": 0.95}}'
        )
        return llm

    def _make_loop(self, llm):
        from memory.memory_manager import MemoryManager
        from reasoning.react_engine import ReasoningLoop
        mem = MemoryManager(agent_id="sim-agent")
        return ReasoningLoop(llm_model=llm, agent_id="sim-agent")

    @pytest.mark.parametrize("task", SIMULATION_TASKS)
    def test_task_completes_without_crash(self, task):
        llm  = self._mock_llm()
        loop = self._make_loop(llm)
        result = loop.run(task, max_iterations=3)
        assert isinstance(result, dict)
        assert "status" in result

    def test_high_confidence_triggers_completion(self):
        """Confidence >= 0.9 should end the loop early."""
        llm = self._mock_llm(
            'THINK: Done.\nACTION: {"tool": "complete", "args": {"result": "summary here", "confidence": 0.95}}'
        )
        loop = self._make_loop(llm)
        result = loop.run("Summarize the doc", max_iterations=10)
        assert result.get("iterations", 99) <= 2


class TestFailureInjection:
    """Simulate failures and verify the system handles them gracefully."""

    def test_tool_not_found_returns_error(self):
        from core.tool_router import ToolRouter
        router = ToolRouter(agent_id="inject-agent")

        # Grant permission so we reach the registry lookup
        router.permissions.grant("nonexistent_tool")

        result = router.execute("nonexistent_tool", {})
        assert result["status"] in ("error", "blocked")

    def test_permission_denied_blocks_dangerous_tool(self):
        from core.tool_router import ToolRouter
        router = ToolRouter(agent_id="no-perms-agent")
        result = router.execute("gmail.send", {"to": "x@y.com", "body": "hi"})
        assert result["status"] == "blocked"
        assert "permission" in result["reason"].lower()

    def test_rate_limit_blocks_excessive_calls(self):
        """Flood a tool call beyond the limit and expect rate_limited."""
        from core.rate_limiter import RateLimiter
        import core.rate_limiter as rl_mod

        call_count = [0]

        class CountingMockPipe:
            def zremrangebyscore(self, *a): pass
            def zcard(self, *a): pass
            def zadd(self, *a): pass
            def expire(self, *a): pass
            def execute(self_inner):
                call_count[0] += 1
                # Simulate 11 existing requests (over the limit of 10)
                return [None, 11, None, None]

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = CountingMockPipe()

        original = rl_mod._redis
        rl_mod._redis = mock_redis
        limiter = RateLimiter()
        result = limiter.allow_tool("agent-x", "gmail.send", limit=10, window_seconds=30)
        rl_mod._redis = original

        assert result is False

    def test_planner_low_confidence_triggers_refine(self):
        """A one-step trivial plan should score below threshold and trigger refinement."""
        from reasoning.planner import DynamicPlanner, CONFIDENCE_THRESHOLD

        weak_plan = [{"step": 1, "description": "Do it."}]  # missing tool, criteria, short desc

        llm = MagicMock()
        # First call returns weak plan; second call returns good plan
        good_plan_json = (
            '[{"step":1,"description":"Search the web for Python 3.13 changelog","expected_tool":"web_search","success_criteria":"Found release notes"},'
            '{"step":2,"description":"Summarize the key new features in plain English","expected_tool":"summarizer","success_criteria":"Summary is clear"}]'
        )
        llm.generate.side_effect = [
            '[{"step":1,"description":"Do it."}]',  # weak
            good_plan_json,                          # refined
        ]

        planner = DynamicPlanner(llm)
        plan = planner.generate_plan("summarize Python 3.13 features")

        # After refinement we should get a proper plan
        assert len(plan) >= 2
        assert all("description" in s for s in plan)

    def test_api_failure_returns_error_not_crash(self):
        """If the tool function raises an unexpected exception, status should be 'error'."""
        from core.tool_router import ToolRouter
        from tools.registry import registry

        # Register a temporary broken tool
        def broken_tool(**kwargs):
            raise RuntimeError("Simulated API timeout")

        registry.register("broken_api", broken_tool, description="a broken tool")

        router = ToolRouter(agent_id="crash-test-agent")
        router.permissions.grant("broken_api")

        result = router.execute("broken_api", {})
        assert result["status"] == "error"
        assert "Simulated API timeout" in result.get("reason", "")
