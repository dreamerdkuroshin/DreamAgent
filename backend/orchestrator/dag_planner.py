"""
backend/orchestrator/dag_planner.py

DAG Planner.
Parses steps with dependencies and creates execution waves.
"""
import logging
from typing import List, Dict, Any, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class PlanStep:
    id: str
    task: str
    depends_on: List[str] = field(default_factory=list)

class DAGPlanner:
    def parse_plan(self, plan_data: List[Dict[str, Any]]) -> List[PlanStep]:
        """Parses planner output into a list of PlanSteps."""
        steps = []
        for i, item in enumerate(plan_data):
            # Normalization
            step_id = item.get("id", f"step_{i+1}")
            task = item.get("task", str(item))
            depends_on = item.get("depends_on", [])
            steps.append(PlanStep(id=step_id, task=task, depends_on=depends_on))
        return steps

    def get_execution_waves(self, steps: List[PlanStep]) -> List[List[PlanStep]]:
        """
        Group steps into waves respecting dependencies.
        Wave 1: no dependencies
        Wave 2: depends on Wave 1, etc.
        """
        waves = []
        remaining = {s.id: s for s in steps}
        completed: Set[str] = set()
        
        # Prevent infinite loops in case of cycles
        max_iterations = len(steps)
        iterations = 0
        
        while remaining and iterations < max_iterations:
            wave = []
            for step_id, step in list(remaining.items()):
                # If all dependencies are in the 'completed' set, it can run this wave
                if all(dep in completed for dep in step.depends_on):
                    wave.append(step)
            
            if not wave:
                # Cycle detected or missing dependency
                logger.error("[DAGPlanner] Cycle detected or unresolvable dependencies. Forcing remaining into final wave.")
                wave = list(remaining.values())
                
            waves.append(wave)
            for step in wave:
                completed.add(step.id)
                if step.id in remaining:
                    del remaining[step.id]
                    
            iterations += 1
            
        return waves

# Singleton
dag_planner = DAGPlanner()
