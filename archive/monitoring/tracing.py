"""
monitoring/tracing.py
Agent tracer with bounded event storage and output sanitisation.

Previous version: self.events and self.active_traces grew unbounded —
a long-running server would OOM after enough traced calls.  Also, result
and error strings from tool calls were stored verbatim, potentially
capturing API keys or tokens that appeared in error messages.

This version:
  - Caps the global events list at MAX_TRACE_EVENTS (env-configurable).
  - Truncates result/error strings before storage.
  - clear_old_traces() is thread-safe.
"""

import logging
import os
import re
import time
import json
from collections import defaultdict
from datetime import datetime
from threading import RLock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_EVENTS      = int(os.getenv("MAX_TRACE_EVENTS", "2000"))
_MAX_STRING_LEN  = 2000   # max chars stored for result/error strings

# Rudimentary credential scrubber for traced data.
_CRED_RE = re.compile(
    r'(bearer\s+|token[=:]\s*|key[=:]\s*|secret[=:]\s*)[^\s"\']{8,}',
    re.IGNORECASE,
)


def _sanitize(value: Any, max_len: int = _MAX_STRING_LEN) -> str:
    """Truncate and scrub credentials from a value before storing it."""
    text = str(value) if value is not None else ""
    text = _CRED_RE.sub(r"\1[REDACTED]", text)
    if len(text) > max_len:
        text = text[:max_len] + "…[truncated]"
    return text


class TraceEvent:
    def __init__(self, event_type: str, data: Dict[str, Any], timestamp: Optional[float] = None):
        self.event_type = event_type
        self.timestamp  = timestamp or time.time()
        self.trace_id   = data.get("trace_id") or f"trace_{int(self.timestamp * 1_000_000)}"
        # Sanitize all string values in data before storing
        self.data = {k: _sanitize(v) if isinstance(v, str) else v for k, v in data.items()}
        self.data["trace_id"] = self.trace_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data":       self.data,
            "timestamp":  self.timestamp,
            "trace_id":   self.trace_id,
        }


class AgentTracer:
    def __init__(self):
        self._lock         = RLock()
        self.events: List[TraceEvent]                      = []
        self.active_traces: Dict[str, List[TraceEvent]]   = defaultdict(list)
        self.performance_metrics: Dict[str, List[float]]  = defaultdict(list)

    def _append_event(self, event: TraceEvent):
        """Append to events list, enforcing the size cap."""
        with self._lock:
            if len(self.events) >= _MAX_EVENTS:
                self.events.pop(0)
            self.events.append(event)
            self.active_traces[event.trace_id].append(event)

    def start_trace(self, operation: str, metadata: Dict[str, Any] = None) -> str:
        event = TraceEvent("trace_start", {"operation": operation, "metadata": metadata or {}})
        self._append_event(event)
        logger.info("Started trace %s for operation: %s", event.trace_id, operation)
        return event.trace_id

    def end_trace(self, trace_id: str, result: Any = None, error: Exception = None):
        event_type = "trace_error" if error else "trace_end"
        event = TraceEvent(event_type, {
            "trace_id": trace_id,
            "result":   _sanitize(result),
            "error":    _sanitize(error),
        })
        self._append_event(event)

        with self._lock:
            events = self.active_traces.get(trace_id, [])
        if len(events) >= 2:
            duration = event.timestamp - events[0].timestamp
            with self._lock:
                self.performance_metrics["trace_duration"].append(duration)
            logger.info("Completed trace %s in %.3fs", trace_id, duration)

    def log_event(self, event_type: str, data: Dict[str, Any], trace_id: str = None):
        if trace_id:
            data = {**data, "trace_id": trace_id}
        event = TraceEvent(event_type, data)
        self._append_event(event)

    def log_tool_usage(self, tool_name: str, input_data: Any, output_data: Any, trace_id: str = None):
        self.log_event("tool_usage", {
            "tool_name": tool_name,
            "input":     _sanitize(input_data),
            "output":    _sanitize(output_data),
        }, trace_id)

    def log_thought(self, thought: str, trace_id: str = None):
        self.log_event("thought", {"content": thought[:1000]}, trace_id)

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self.active_traces.get(trace_id, [])]

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self.events[-limit:]]

    def get_performance_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = {}
            for metric, values in self.performance_metrics.items():
                if values:
                    stats[metric] = {
                        "count": len(values),
                        "avg":   round(sum(values) / len(values), 4),
                        "min":   round(min(values), 4),
                        "max":   round(max(values), 4),
                    }
            return stats

    def export_trace(self, trace_id: str, filepath: str):
        data = {
            "trace_id":    trace_id,
            "events":      self.get_trace(trace_id),
            "exported_at": datetime.now().isoformat(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def clear_old_traces(self, max_age_seconds: int = 3600):
        cutoff = time.time() - max_age_seconds
        with self._lock:
            self.events = [e for e in self.events if e.timestamp > cutoff]
            stale = [tid for tid, evts in self.active_traces.items()
                     if evts and evts[0].timestamp <= cutoff]
            for tid in stale:
                del self.active_traces[tid]

    def get_error_events(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self.events if e.event_type == "trace_error"]

    def get_success_rate(self) -> float:
        with self._lock:
            total = len(self.active_traces)
            if total == 0:
                return 0.0
            successful = sum(
                1 for evts in self.active_traces.values()
                if len(evts) >= 2 and evts[-1].event_type == "trace_end"
            )
            return round(successful / total, 4)


global_tracer = AgentTracer()


def get_tracer() -> AgentTracer:
    return global_tracer
