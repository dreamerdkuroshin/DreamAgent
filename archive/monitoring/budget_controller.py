"""
monitoring/budget_controller.py
Thread-safe budget controller with separate check and record phases.

Breaking change from previous version:
  can_spend() is REMOVED.  It debited on check, making it unsafe for
  concurrent agents and impossible to roll back on API failure.

  New API:
    ok, reason = controller.check_budget(amount, service)
    if ok:
        try:
            result = call_api(...)
            controller.record_spend(amount, service)   # only after success
        except ApiError:
            pass  # budget NOT debited — no rollback needed
"""

import threading
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when a spend would exceed configured budget limits."""


class BudgetController:
    """
    Enforce budget limits across concurrent agents.

    Thread-safe via a reentrant lock.  check_budget() and record_spend()
    are deliberately separate operations so that a failed API call does
    not consume budget.
    """

    def __init__(self, total_budget: float = 0.0):
        self.total_budget = total_budget
        self._spent = 0.0
        self._limits_by_service: Dict[str, float] = {}
        self._spent_by_service: Dict[str, float] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Configuration (call at startup)
    # ------------------------------------------------------------------

    def set_budget(self, amount: float) -> None:
        with self._lock:
            self.total_budget = amount

    def set_service_limit(self, service: str, limit: float) -> None:
        with self._lock:
            self._limits_by_service[service] = limit
            self._spent_by_service.setdefault(service, 0.0)

    # ------------------------------------------------------------------
    # Two-phase spend API
    # ------------------------------------------------------------------

    def check_budget(
        self, amount: float, service: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check whether spending `amount` would stay within budget.

        Does NOT debit the budget — call record_spend() after a successful
        API call.  Safe to call from multiple threads simultaneously.

        Returns:
            (True, None)           — spend is within limits.
            (False, reason_string) — spend would exceed a limit.
        """
        with self._lock:
            if self.total_budget > 0 and self._spent + amount > self.total_budget:
                return (
                    False,
                    f"Total budget would be exceeded. "
                    f"Spent: ${self._spent:.4f}, Limit: ${self.total_budget:.4f}",
                )

            if service and service in self._limits_by_service:
                svc_limit = self._limits_by_service[service]
                svc_spent = self._spent_by_service.get(service, 0.0)
                if svc_limit > 0 and svc_spent + amount > svc_limit:
                    return (
                        False,
                        f"Service budget for '{service}' would be exceeded. "
                        f"Spent: ${svc_spent:.4f}, Limit: ${svc_limit:.4f}",
                    )

        return True, None

    def record_spend(self, amount: float, service: Optional[str] = None) -> None:
        """
        Record a confirmed spend AFTER a successful API call.

        Call this only when the upstream call succeeded.  If the API call
        fails, do NOT call record_spend — the budget is not debited.
        """
        if amount <= 0:
            return
        with self._lock:
            self._spent += amount
            if service:
                self._spent_by_service[service] = (
                    self._spent_by_service.get(service, 0.0) + amount
                )
        logger.debug(
            "BudgetController: recorded $%.6f for service='%s'. Total: $%.4f",
            amount, service, self._spent,
        )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @property
    def total_spent(self) -> float:
        with self._lock:
            return self._spent

    def get_report(self) -> dict:
        with self._lock:
            return {
                "total_budget": self.total_budget,
                "total_spent": self._spent,
                "remaining": max(0.0, self.total_budget - self._spent),
                "by_service": dict(self._spent_by_service),
            }
