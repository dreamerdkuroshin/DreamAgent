"""
backend/core/tool_tracker.py

Dragonfly-backed tool performance tracking.
Tracks call counts, failures, and rolling latency for each tool.
Exposes data for intelligent routing and frontend monitoring.
"""

import time
import logging
from typing import Dict, Any

from backend.core.dragonfly_manager import dragonfly

logger = logging.getLogger(__name__)

class ToolTracker:
    def _get_client(self):
        return dragonfly.get_client()

    def record_call(self, tool_name: str, success: bool, latency_ms: int):
        """Record the outcome of a tool call."""
        client = self._get_client()
        if not client:
            return  # Skip silently if redis is down
        
        try:
            # Increment total calls
            client.incr(f"tool_stat:{tool_name}:calls")
            
            # Increment failures
            if not success:
                client.incr(f"tool_stat:{tool_name}:failures")
                
            # Add to rolling latency (last 100 calls)
            latency_key = f"tool_stat:{tool_name}:latency"
            client.lpush(latency_key, str(latency_ms))
            client.ltrim(latency_key, 0, 99)
        except Exception as e:
            logger.error(f"[ToolTracker] Error recording call for {tool_name}: {e}")

    def get_stats(self, tool_name: str) -> Dict[str, Any]:
        """Fetch statistics for a single tool."""
        client = self._get_client()
        if not client:
            return {"calls": 0, "failures": 0, "success_rate": 100.0, "avg_latency_ms": 0.0}
            
        try:
            calls = int(client.get(f"tool_stat:{tool_name}:calls") or 0)
            failures = int(client.get(f"tool_stat:{tool_name}:failures") or 0)
            
            latencies_raw = client.lrange(f"tool_stat:{tool_name}:latency", 0, -1)
            latencies = [int(l) for l in latencies_raw] if latencies_raw else []
            
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
            success_rate = ((calls - failures) / calls * 100.0) if calls > 0 else 100.0
            
            return {
                "calls": calls,
                "failures": failures,
                "success_rate": round(success_rate, 2),
                "avg_latency_ms": round(avg_latency, 2)
            }
        except Exception as e:
            logger.error(f"[ToolTracker] Error fetching stats for {tool_name}: {e}")
            return {"calls": 0, "failures": 0, "success_rate": 100.0, "avg_latency_ms": 0.0}

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Fetch statistics for all monitored tools."""
        client = self._get_client()
        if not client:
            return {}
            
        try:
            # Find all recorded tools
            keys = client.keys("tool_stat:*:calls")
            # keys are bytes in some redis clients, handle appropriately
            if isinstance(keys, list) and len(keys) > 0 and isinstance(keys[0], bytes):
                keys = [k.decode('utf-8') for k in keys]
                
            tool_names = [k.split(":")[1] for k in keys]
            
            stats = {}
            for t in tool_names:
                stats[t] = self.get_stats(t)
            return stats
        except Exception as e:
            logger.error(f"[ToolTracker] Error fetching all stats: {e}")
            return {}

# Singleton instance
tool_tracker = ToolTracker()
