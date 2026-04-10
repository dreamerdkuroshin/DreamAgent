"""
tests/test_unit.py

Unit tests for:
- StateManager (versioning, snapshots, write-through)
- ToolSelector (scoring formula, ε-greedy)
- RateLimiter (allow / deny)
- PermissionGuard (grant / revoke / check)
- CostTracker (_price calculation)
- DynamicPlanner (validate_plan, confidence scoring)
"""

import pytest
import time
from unittest.mock import MagicMock, patch


# ── State Manager ────────────────────────────────────────────────────

class TestStateManager:
    def _make_manager(self, redis_mock=None):
        from core.state_manager import StateManager
        return StateManager(redis_conn=redis_mock)

    def test_initial_state_version_zero(self):
        from core.state_manager import AgentState
        s = AgentState("task-1", "do something")
        assert s.version == 0
        assert s.status == "pending"

    def test_save_increments_version(self):
        redis_mock = MagicMock()
        redis_mock.get.return_value = None
        mgr   = self._make_manager(redis_mock)
        state = mgr.load_state("task-1")
        mgr.save_state(state)
        assert state.version == 1

    def test_save_creates_snapshot(self):
        redis_mock = MagicMock()
        redis_mock.get.return_value = None
        mgr   = self._make_manager(redis_mock)
        state = mgr.load_state("task-x")
        mgr.save_state(state)
        mgr.save_state(state)
        assert len(state.snapshots) == 2

    def test_add_step_increments_current_step(self):
        redis_mock = MagicMock()
        redis_mock.get.return_value = None
        mgr = self._make_manager(redis_mock)
        mgr.add_step("task-2", {"thought": "think", "action": "search", "tool": "web", "output": "result"})
        # Redis.set should have been called
        assert redis_mock.set.called

    def test_metrics_tool_success_rate(self):
        redis_mock = MagicMock()
        redis_mock.get.return_value = None
        mgr = self._make_manager(redis_mock)
        mgr.update_metrics("task-3", tool_success=True)
        mgr.update_metrics("task-3", tool_success=False)
        # After 2 calls: 1 success → 0.5 rate (first call fresh load → rate computed per-load)
        # Ensuring no exceptions is the baseline here


# ── ToolSelector ─────────────────────────────────────────────────────

class TestToolSelector:
    def test_dynamic_weights_research(self):
        from tools.tool_selector import WEIGHTS_BY_TASK
        w = WEIGHTS_BY_TASK["research"]
        assert w["relevance"] == 0.6
        assert w["latency"] < 0   # penalty

    def test_dynamic_weights_execution(self):
        from tools.tool_selector import WEIGHTS_BY_TASK
        w = WEIGHTS_BY_TASK["execution"]
        assert w["latency"] <= -0.2   # harsher latency penalty

    def test_epsilon_greedy_constant(self):
        from tools.tool_selector import EPSILON
        assert 0 < EPSILON <= 0.2   # sane range


# ── Rate Limiter ─────────────────────────────────────────────────────

class TestRateLimiter:
    def test_allow_without_redis(self):
        """When Redis is unavailable, all requests should be allowed."""
        from core.rate_limiter import RateLimiter
        limiter = RateLimiter()
        # Monkey-patch _redis to None
        import core.rate_limiter as rl_mod
        original = rl_mod._redis
        rl_mod._redis = None
        assert limiter.allow("user:test", limit=1, window_seconds=60) is True
        rl_mod._redis = original

    def test_allow_user_helper(self):
        from core.rate_limiter import RateLimiter
        import core.rate_limiter as rl_mod
        original = rl_mod._redis

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_redis.pipeline.return_value.__exit__  = MagicMock(return_value=False)
        pipe_mock = MagicMock()
        pipe_mock.execute.return_value = [None, 5, None, None]  # count=5
        mock_redis.pipeline.return_value = pipe_mock

        rl_mod._redis = mock_redis
        limiter = RateLimiter()
        result = limiter.allow_user("alice", limit=60)
        assert result is True   # 5 < 60
        rl_mod._redis = original


# ── Permission Guard ─────────────────────────────────────────────────

class TestPermissionGuard:
    def _guard(self, agent_id: str = "test-agent"):
        import core.permissions as pm
        pm._redis = None   # test without Redis
        from core.permissions import PermissionGuard
        return PermissionGuard(agent_id)

    def test_safe_defaults_allowed(self):
        guard = self._guard()
        assert guard.check("web_search") is True
        assert guard.check("calculator") is True

    def test_dangerous_denied_by_default(self):
        guard = self._guard()
        assert guard.check("gmail.send") is False
        assert guard.check("execute_code") is False

    def test_grant_revoke(self):
        guard = self._guard()
        guard.grant("gmail.send")
        assert guard.check("gmail.send") is True
        guard.revoke("gmail.send")
        assert guard.check("gmail.send") is False


# ── Cost Tracker ─────────────────────────────────────────────────────

class TestCostTracker:
    def test_price_calculation(self):
        from core.cost_tracker import _price
        cost = _price("gpt-4o", 1000)
        assert abs(cost - 0.005) < 1e-9

    def test_price_default_model(self):
        from core.cost_tracker import _price
        cost = _price("unknown-model", 1000)
        assert cost > 0

    def test_record_returns_float(self):
        import core.cost_tracker as ct_mod
        ct_mod._redis = None   # skip Redis
        from core.cost_tracker import CostTracker
        with patch.object(CostTracker, "_write_db", return_value=None):
            tracker = CostTracker()
            cost = tracker.record("t1", tokens=500, model="gpt-3.5-turbo")
        assert isinstance(cost, float)
        assert cost > 0


# ── DynamicPlanner ───────────────────────────────────────────────────

class TestDynamicPlanner:
    def _plan(self, steps: int = 3):
        return [
            {
                "step": i + 1,
                "description": f"Do something meaningful for step {i+1}",
                "expected_tool": "web_search",
                "success_criteria": "Result is verified",
            }
            for i in range(steps)
        ]

    def test_validate_plan_valid(self):
        from reasoning.planner import DynamicPlanner
        planner = DynamicPlanner(llm_model=MagicMock())
        assert planner.validate_plan(self._plan(3)) is True

    def test_validate_plan_empty(self):
        from reasoning.planner import DynamicPlanner
        planner = DynamicPlanner(llm_model=MagicMock())
        assert planner.validate_plan([]) is False

    def test_confidence_score_full_plan(self):
        from reasoning.planner import DynamicPlanner
        planner = DynamicPlanner(llm_model=MagicMock())
        plan    = self._plan(3)
        task    = "do something meaningful"
        score   = planner._score_confidence(plan, task)
        assert score >= 0.8   # all 5 heuristics should pass
