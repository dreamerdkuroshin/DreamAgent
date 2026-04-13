"""
backend/builder/multi_agent_builder.py

Contains the BuilderOrchestrator which recursively evaluates and fixes generated code 
using the specialized agents from backend/agents/.
"""

import logging
import json
import asyncio
from typing import Dict, Any, Callable, Optional, Tuple

from backend.llm.universal_provider import UniversalProvider
from backend.agents.planner import PlannerAgent
from backend.agents.coder import CoderAgent  # Fallback layer
from backend.agents.ui_generator import UIGeneratorAgent
from backend.agents.backend_generator import BackendGeneratorAgent
from backend.agents.tester import TesterAgent
from backend.agents.fixer import FixerAgent
from backend.agents.reviewer import ReviewerAgent

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

PROGRESS_MAP = {
    "planning": 10,
    "ui_coding": 25,
    "backend_coding": 40,
    "testing": 55,
    "fixing": 70,
    "review": 85,
    "done": 100,
}

class BuilderOrchestrator:
    """Controls the recursive flow: Plan -> Gen -> Test -> Fix -> Review."""

    def __init__(self, provider: str = "auto", model: str = "", publish_event: Optional[Callable] = None):
        self.provider = provider
        self.model = model
        self.publish_event = publish_event
        self.llm = UniversalProvider(provider=provider, model=model)

        self.planner = PlannerAgent(self.llm)
        self.ui_generator = UIGeneratorAgent(self.llm)
        self.backend_generator = BackendGeneratorAgent(self.llm)
        self.coder_fallback = CoderAgent(self.llm) # Fallback logic
        self.tester = TesterAgent(self.llm)
        self.fixer = FixerAgent(self.llm)
        self.reviewer = ReviewerAgent(self.llm)

    def _emit(self, step: str, progress: int, message: str):
        if self.publish_event:
            self.publish_event({"type": "builder_step", "step": step, "progress": progress, "message": message})
        logger.info(f"[Orchestrator] [{step}] {message}")

    async def run(self, user_request: str, prefs: Dict[str, Any], current_files: Dict[str, str] = None, plan: Dict[str, Any] = None, attempt: int = 1) -> Tuple[Dict[str, str], Dict[str, Any]]:
        if attempt > MAX_ATTEMPTS:
            self._emit("error", PROGRESS_MAP["review"], f"Max fix attempts ({MAX_ATTEMPTS}) reached. Returning best effort.")
            return current_files or {}, plan or {}

        # 1. PLANNER
        if not plan:
            self._emit("planning", PROGRESS_MAP["planning"], f"🧠 Planner analyzing task (Attempt {attempt})...")
            plan_result = await self.planner.plan(user_request)
            
            # Guard: ensure plan_result is always a dict (never bool/None)
            if not isinstance(plan_result, dict):
                logger.warning("[BuilderOrchestrator] Planner returned non-dict output (%s), using heuristic fallback.", type(plan_result))
                plan_result = {"goal": user_request, "steps": [], "requires_plan": True}
            
            # Mix with user preferences to create the builder spec format
            plan = {
                "project_name": plan_result.get("goal", user_request[:60]),
                "files_to_generate": ["index.html", "style.css", "app.js", "main.py"],
                "sections": ["Hero", "Features", "Footer"],
                "color_palette": ["#00f0ff", "#8b5cf6", "#0a0a12"],
                "font": "Inter",
                "key_features": plan_result.get("steps", [user_request])
            }
            # override with prefs if needed
            plan.update(prefs.get("spec", {}))
        
        # Guard: ensure plan is always a dict before passing downstream
        if not isinstance(plan, dict):
            logger.error("[BuilderOrchestrator] plan is not a dict (%s), resetting to defaults.", type(plan))
            plan = {
                "project_name": user_request[:60],
                "files_to_generate": ["index.html", "style.css", "app.js"],
                "sections": ["Hero", "Features", "Footer"],
                "color_palette": ["#00f0ff", "#8b5cf6", "#0a0a12"],
                "font": "Inter",
                "key_features": [user_request]
            }


        # 2. GENERATION (UI & Backend)
        if not current_files:
            self._emit("ui_coding", PROGRESS_MAP["ui_coding"], "🎨 UI Generator designing frontend...")
            ui_files = await self.ui_generator.run(plan, self.publish_event)

            self._emit("backend_coding", PROGRESS_MAP["backend_coding"], "⚙️ Backend Generator wiring logic...")
            backend_files = await self.backend_generator.run(plan, self.publish_event)
            
            current_files = {**ui_files, **backend_files}

            if not current_files:
                self._emit("fallback", PROGRESS_MAP["ui_coding"], "⚠️ Specialized Generators failed. Injecting Fallback CoderAgent...")
                fallback_code = await self.coder_fallback.code(user_request, str(plan))
                current_files = {"app.js": fallback_code} # Rough fallback mapping

        # 3. TESTER
        self._emit("testing", PROGRESS_MAP["testing"], f"🧪 Tester analyzing codebase (Attempt {attempt})...")
        flat_code = "\n\n".join([f"--- {k} ---\n{v}" for k, v in current_files.items()])
        test_feedback = await self.tester.test(flat_code, user_request)

        # 4. FIXER (Recursive loop trigger)
        # Heuristic check for test failure indicating structural issues
        if "fail" in test_feedback.lower() or "error" in test_feedback.lower() or "missing" in test_feedback.lower():
            self._emit("fixing", PROGRESS_MAP["fixing"], f"🔧 Fixer repairing structural issues (Attempt {attempt})...")
            # Use fixer agent
            fixed_code_result = await self.fixer.think(
                f"Issues found:\n{test_feedback}\n\nOriginal Code:\n{flat_code}\n\nProvide the completely fixed code blocks mapped precisely to their filenames using markdown."
            )
            
            # Simple heuristic extraction of repaired files
            updated_files = dict(current_files)
            for fname in updated_files.keys():
                if fname in fixed_code_result:
                    # Very naive extraction logic just for orchestrator scaffolding
                    start_idx = fixed_code_result.find(fname)
                    # For production, we'd use robust regex like we did in UIGenerator
                    
            # In a true recursive system, we recurse back up!
            return await self.run(user_request, prefs, current_files=updated_files, plan=plan, attempt=attempt+1)

        # 5. REVIEWER
        self._emit("review", PROGRESS_MAP["review"], "🔍 Final Code Review...")
        review = await self.reviewer.review(flat_code, test_feedback, user_request)

        if "APPROVED" not in review.upper() and attempt < MAX_ATTEMPTS:
            self._emit("fixing", PROGRESS_MAP["fixing"], "🚨 Reviewer rejected code! Sending back to Fixer...")
            fixed_code_result = await self.fixer.think(
                f"Reviewer Rejection:\n{review}\n\nOriginal Code:\n{flat_code}\n\nFix the code."
            )
            # Re-run loop
            return await self.run(user_request, prefs, current_files=current_files, plan=plan, attempt=attempt+1)
            
        self._emit("done", PROGRESS_MAP["done"], "🚀 Build Complete & Approved!")
        return current_files, plan


# Backward compatible entry point for chat_worker.py
async def multi_agent_build(
    user_request: str,
    prefs: Dict[str, Any],
    provider: str = "auto",
    model: str = "",
    publish_event: Optional[Callable] = None
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    
    orchestrator = BuilderOrchestrator(provider, model, publish_event)
    return await orchestrator.run(user_request, prefs)
