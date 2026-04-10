"""Reflect on and consolidate memories for improved learning."""

from typing import Dict, List, Any
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class MemoryReflection:
    """Reflect on accumulated memories to improve understanding."""

    def __init__(self):
        """Initialize memory reflection."""
        self.memories: List[Dict[str, Any]] = []
        self.insights: List[str] = []

    def add_memory(self, memory: Dict[str, Any]) -> None:
        """Add a memory to reflect on.
        
        Args:
            memory: Memory to store
        """
        self.memories.append(memory)

    def reflect(self) -> List[str]:
        """Reflect on accumulated memories.
        
        Returns:
            List of insights generated from reflection
        """
        if not self.memories:
            return []

        new_insights = []
        
        # Group memories by type
        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for m in self.memories:
            by_type[m.get("type", "general")].append(m)

        for mtype, items in by_type.items():
            # Detect recurring outcomes
            outcomes = [m.get("outcome") for m in items if m.get("outcome")]
            if outcomes:
                most_common = max(set(outcomes), key=outcomes.count)
                freq = outcomes.count(most_common)
                if freq > 1:
                    new_insights.append(f"Recurring outcome in '{mtype}': {most_common} (seen {freq} times)")

            # Surface recency patterns
            recent_items = items[-3:] if len(items) >= 3 else items
            if all(m.get("success") for m in recent_items if "success" in m):
                new_insights.append(f"Recent success streak in type '{mtype}'.")
            elif all(not m.get("success") for m in recent_items if "success" in m):
                new_insights.append(f"Recent failure streak in type '{mtype}'. Needs attention.")

        self.insights.extend(new_insights)
        # Deduplicate
        self.insights = list(dict.fromkeys(self.insights))
        
        return new_insights

    def consolidate_learning(self) -> Dict[str, Any]:
        """Consolidate learning from all memories.
        
        Returns:
            Consolidated learning data
        """
        by_type = defaultdict(list)
        for m in self.memories:
            by_type[m.get("type", "general")].append(m)

        success_rate_per_type = {}
        key_lessons = []

        for mtype, items in by_type.items():
            successes = sum(1 for m in items if m.get("success"))
            total = len([m for m in items if "success" in m])
            if total > 0:
                success_rate_per_type[mtype] = successes / total
            
            # Simple lesson extraction
            lessons = [m.get("lesson") for m in items if m.get("lesson")]
            if lessons:
                key_lessons.extend(lessons)

        return {
            "success_rate_per_type": success_rate_per_type,
            "key_lessons": list(dict.fromkeys(key_lessons)),
            "all_insights": self.insights
        }

    def get_insights(self) -> List[str]:
        """Get insights from memory reflection."""
        return self.insights
