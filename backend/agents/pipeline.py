"""
backend/agents/pipeline.py

Multi-Agent Execution Pipeline:
Planner -> Coder -> Tester -> Fixer -> Reviewer
"""
import logging
from typing import Callable, Any, Dict, Optional

from backend.agents.planner import PlannerAgent
from backend.agents.coder import CoderAgent
from backend.agents.tester import TesterAgent
from backend.agents.fixer import FixerAgent
from backend.agents.reviewer import ReviewerAgent
from backend.llm.universal_provider import UniversalProvider

logger = logging.getLogger(__name__)

MAX_FIX_ATTEMPTS = 2

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    if not text: return 0
    return max(1, len(str(text)) // 4)

class MultiAgentPipeline:
    """
    Coordinates a sequential chain of specialized agents to accomplish a task.
    Flow: User Input -> Planner -> Coder -> Tester -> Fixer -> Reviewer -> Final Output
    """
    def __init__(self, provider: str = "auto", model: str = ""):
        self.llm = UniversalProvider(provider=provider, model=model)
        self.planner = PlannerAgent(self.llm)
        self.coder = CoderAgent(self.llm)
        self.tester = TesterAgent(self.llm)
        self.fixer = FixerAgent(self.llm)
        self.reviewer = ReviewerAgent(self.llm)

    async def run(self, task: str, publish: Optional[Callable[[Dict[str, Any]], None]] = None, task_ctx=None) -> str:
        def _pub(msg: str):
            if publish:
                publish({
                    "type": "agent",
                    "agent": "pipeline",
                    "role": "system",
                    "status": "running",
                    "content": msg
                })
                
        def _charge(text: Any, stage: str):
            """Charge estimated tokens against the budget."""
            if task_ctx and hasattr(task_ctx, 'track_tokens'):
                tokens = _estimate_tokens(str(text))
                task_ctx.track_tokens(tokens)
                logger.info(f"[Pipeline] stage={stage} tokens_charged={tokens} total={task_ctx.token_usage}")

        pipeline_context = {
            "plan": "",
            "code": "",
            "tests": "",
            "errors": [],
            "stages": {
                "planner": "pending",
                "coder": "pending",
                "tester": "pending",
                "fixer": "pending",
                "reviewer": "pending"
            }
        }
        
        # --- Stage 1: Planner ---
        try:
            _pub("📝 [Step 1/5] Planner analyzing task...")
            pipeline_context["stages"]["planner"] = "running"
            plan_dict = await self.planner.plan(task)
            
            # Format the plan steps
            if plan_dict.get("requires_plan") and plan_dict.get("steps"):
                plan_str = "\\n".join(f"{i+1}. {s}" for i, s in enumerate(plan_dict["steps"]))
            else:
                plan_str = f"Direct execution:\\n1. {task}"
                
            pipeline_context["plan"] = plan_str
            pipeline_context["stages"]["planner"] = "completed"
            _charge(plan_str, "planner")
        except Exception as e:
            pipeline_context["stages"]["planner"] = "failed"
            pipeline_context["errors"].append(f"Planner Error: {str(e)}")
            raise
            
        # --- Stage 2: Coder ---
        try:
            _pub(f"👨‍💻 [Step 2/5] Coder implementing plan:\\n\\n{pipeline_context['plan']}")
            pipeline_context["stages"]["coder"] = "running"
            pipeline_context["code"] = await self.coder.code(task=task, context=pipeline_context["plan"])
            pipeline_context["stages"]["coder"] = "completed"
            _charge(pipeline_context["code"], "coder")
        except Exception as e:
            pipeline_context["stages"]["coder"] = "failed"
            pipeline_context["errors"].append(f"Coder Error: {str(e)}")
            raise

        # --- Stage 3: Tester ---
        try:
            _pub("🧪 [Step 3/5] Tester writing verification suite...")
            pipeline_context["stages"]["tester"] = "running"
            pipeline_context["tests"] = await self.tester.test(code_implementation=pipeline_context["code"], task=task)
            pipeline_context["stages"]["tester"] = "completed"
            _charge(pipeline_context["tests"], "tester")
        except Exception as e:
            pipeline_context["stages"]["tester"] = "failed"
            pipeline_context["errors"].append(f"Tester Error: {str(e)}")
            raise

        # --- Stage 4: Fixer ---
        try:
            _pub("🛠️ [Step 4/5] Fixer checking for bugs...")
            pipeline_context["stages"]["fixer"] = "running"
            
            for attempt in range(MAX_FIX_ATTEMPTS):
                fix_result = await self.fixer.fix(code=pipeline_context["code"], tests=pipeline_context["tests"])
                _charge(fix_result, f"fixer_attempt_{attempt+1}")
                
                if "NO_FIX_NEEDED" in fix_result:
                    _pub("✅ Fixer confirmed code is solid. No bugs found.")
                    break
                    
                _pub(f"🔧 Fixer identified issues (Attempt {attempt+1}/{MAX_FIX_ATTEMPTS}). Applying fixes.")
                pipeline_context["code"] = fix_result
                pipeline_context["errors"].append(f"Fixed bug in attempt {attempt+1}")
                
            pipeline_context["stages"]["fixer"] = "completed"
        except Exception as e:
            pipeline_context["stages"]["fixer"] = "failed"
            pipeline_context["errors"].append(f"Fixer Error: {str(e)}")
            raise

        # --- Stage 5: Reviewer ---
        try:
            _pub("👀 [Step 5/5] Reviewer performing final QA check...")
            pipeline_context["stages"]["reviewer"] = "running"
            review = await self.reviewer.review(final_code=pipeline_context["code"], tests=pipeline_context["tests"], original_task=task)
            pipeline_context["stages"]["reviewer"] = "completed"
            _charge(review, "reviewer")
        except Exception as e:
            pipeline_context["stages"]["reviewer"] = "failed"
            pipeline_context["errors"].append(f"Reviewer Error: {str(e)}")
            raise

        _pub("🌟 Multi-Agent Pipeline completed successfully.")
        
        token_usage_str = ""
        if task_ctx and hasattr(task_ctx, 'token_usage'):
            token_usage_str = f"\\n\\n*Tokens used by pipeline: {task_ctx.token_usage}*"
            
        stage_summary = " → ".join(f"{k}:\\u2705" if v == "completed" else f"{k}:\\u274c" for k,v in pipeline_context["stages"].items())
        
        return f"**Final Review & Implementation**\\n\\nPipeline Execution: {stage_summary}\\n\\n{review}{token_usage_str}"
