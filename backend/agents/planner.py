"""
backend/agents/planner.py

PlannerAgent — conditionally breaks a user task into clear, numbered steps.
Returns a dict indicating if a plan is required, and the steps if true.
"""
import json
import logging
from typing import Dict, Any

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

PLANNER_SYSTEM = """You are a master Planner Agent inside a multi-agent AI system.
Your job is to determine if a user's request requires a multi-step execution plan, or if it can be answered directly.

RULES:
1. If the request is a simple question or chat (e.g. "What is python?", "Hi"), set requires_plan to false.
2. If the request requires building, deploying, debugging, or multi-stage research (e.g. "Build me a discord bot", "Debug my python script"), set requires_plan to true.
3. If requires_plan is true, break the goal into clear atomic steps.
4. Respond ONLY with valid JSON matching the schema below. No markdown wrappers.

SCHEMA:
{
  "requires_plan": boolean,
  "goal": "string (the overarching goal)",
  "steps": ["string (step 1)", "string (step 2)"]
}
"""

class PlannerAgent(BaseAgent):
    """Conditionally decomposes a user query into an ordered list of tasks via JSON."""

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools, role="planner")

    async def plan(self, user_input: str) -> Dict[str, Any]:
        """
        Generate a conditional plan.
        Returns a dict: {"requires_plan": bool, "goal": str, "steps": List[str]}
        """
        prompt = f"Analyze and plan the following task:\n\nTASK: {user_input}"
        raw = await self.think(prompt, system=PLANNER_SYSTEM)
        logger.debug("[PlannerAgent] Raw response:\n%s", raw)

        # Clean markdown formatting if the model leaked it
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
            
        try:
            plan_data = json.loads(cleaned.strip())
            return {
                "requires_plan": bool(plan_data.get("requires_plan", False)),
                "goal": str(plan_data.get("goal", user_input)),
                "steps": list(plan_data.get("steps", []))
            }
        except json.JSONDecodeError as e:
            logger.error("[PlannerAgent] Failed to decode JSON plan: %s", e)
            # Fallback heuristic if JSON fully fails
            needs_plan = len(user_input.split()) > 10 or any(x in user_input.lower() for x in ["build", "debug", "create", "write"])
            return {
                "requires_plan": needs_plan,
                "goal": user_input,
                "steps": [user_input] if needs_plan else []
            }
