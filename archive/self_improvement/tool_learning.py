"""Learn from tool usage patterns and improve tool selection."""

from typing import Dict, List, Tuple
import logging
import math

logger = logging.getLogger(__name__)


class ToolLearning:
    """Learn tool usage patterns and improve selection."""

    def __init__(self):
        """Initialize tool learning."""
        self.usage_patterns: Dict[str, int] = {}
        self.success_rates: Dict[str, float] = {}
        self.tool_combinations: Dict[Tuple[str, ...], int] = {}
        # Simple keyword mapping for mock keyword overlap
        self.tool_keywords: Dict[str, List[str]] = {
            "search": ["find", "lookup", "query", "search"],
            "execute": ["run", "execute", "start", "eval"],
            "write": ["create", "save", "write", "output"],
            "read": ["load", "read", "get", "fetch"]
        }

    def record_tool_usage(self, tool_name: str, success: bool) -> None:
        """Record a tool usage occurrence.
        
        Args:
            tool_name: Name of the tool
            success: Whether the usage was successful
        """
        self.usage_patterns[tool_name] = self.usage_patterns.get(tool_name, 0) + 1
        
        # Incremental mean for success rate
        current_rate = self.success_rates.get(tool_name, 0.0)
        n = self.usage_patterns[tool_name]
        
        # new_mean = current_mean + (value - current_mean) / n
        value = 1.0 if success else 0.0
        self.success_rates[tool_name] = current_rate + (value - current_rate) / n

    def get_success_rate(self, tool_name: str) -> float:
        """Get success rate for a tool."""
        return self.success_rates.get(tool_name, 0.0)

    def recommend_tools(self, task: str) -> List[Tuple[str, float]]:
        """Recommend tools for a task based on learned patterns.
        
        Args:
            task: Task description
            
        Returns:
            List of (tool_name, confidence_score) tuples
        """
        if not self.usage_patterns:
            return []
            
        task_lower = task.lower()
        recommendations = []
        
        for tool_name in self.usage_patterns:
            # Calculate keyword overlap score (0.0 to 1.0)
            keywords = self.tool_keywords.get(tool_name, [tool_name.lower()])
            overlap_count = sum(1 for kw in keywords if kw in task_lower)
            keyword_score = min(1.0, overlap_count / max(1, len(keywords)))
            
            # Get success rate
            success_rate = self.success_rates.get(tool_name, 0.0)
            
            # Calculate frequency bonus
            freq = self.usage_patterns.get(tool_name, 0)
            log_freq_bonus = math.log1p(freq) * 0.1 # scaled log factor
            
            # Target formula: 0.6×success_rate + 0.3×keyword_overlap + log_freq_bonus
            score = (0.6 * success_rate) + (0.3 * keyword_score) + log_freq_bonus
            
            recommendations.append((tool_name, score))
            
        # Sort by score descending
        return sorted(recommendations, key=lambda x: x[1], reverse=True)
