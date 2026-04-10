"""
monitoring/metrics.py
Thread-safe metrics counter.

Previous version used class-level attributes — not thread-safe and not
reset-able across tests.  This version uses instance state with a lock.
"""

import threading
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class Metrics:
    """Thread-safe task success/failure counter."""

    def __init__(self):
        self._lock = threading.Lock()
        self._completed = 0
        self._failed = 0
        self._custom: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Core counters
    # ------------------------------------------------------------------

    def success(self):
        with self._lock:
            self._completed += 1

    def failure(self):
        with self._lock:
            self._failed += 1

    def increment(self, key: str, amount: int = 1):
        """Increment an arbitrary named counter."""
        with self._lock:
            self._custom[key] = self._custom.get(key, 0) + amount

    def reset(self):
        """Reset all counters (useful between tests)."""
        with self._lock:
            self._completed = 0
            self._failed = 0
            self._custom.clear()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @property
    def tasks_completed(self) -> int:
        with self._lock:
            return self._completed

    @property
    def tasks_failed(self) -> int:
        with self._lock:
            return self._failed

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "tasks_completed": self._completed,
                "tasks_failed":    self._failed,
                **self._custom,
            }


# Global singleton
metrics = Metrics()
