"""
backend/agents/critic.py

CriticAgent — reviews an executor's output and optionally corrects it.
Implements a self-correction retry loop (up to MAX_RETRIES attempts).
"""
import logging
from typing import Tuple

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

MAX_RETRIES = 1  # Reduced from 3 — was causing up to 24 LLM calls per task

CRITIC_SYSTEM = """You are a Critic Agent in a multi-agent AI system.
Your job is to review the result of an executed task step for:
- Accuracy and correctness
- Completeness (all parts of the step addressed)
- Clarity and quality

CRITICAL CONSTRAINT ON CONTRADICTIONS:
If you detect conflicting logic or data (e.g., source A says X, source B says Y), you MUST NOT produce a blended middle.
You must force the result to:
1. Select the more valid claim (with logical rationale).
2. Define a context split (e.g., "A is true for segment 1, B is true for segment 2").
3. Declare insufficient data and flag as UNRESOLVED_CONTRADICTION.

CRITICAL CONSTRAINT ON CODE REVIEW:
If you are reviewing code, you cannot execute it. You MUST NOT claim "all tests passed" or simulate a terminal output. 
You must perform static analysis only, and end your review with exactly: "Static Analysis Complete - Manual Execution Required."

If the result is satisfactory, respond with exactly: VALID

If the result has issues, respond with:
NEEDS_IMPROVEMENT: <reason, e.g., Unresolved Contradiction Detected>
CORRECTED:
<your improved/decisive version of the result>
"""


class CriticAgent(BaseAgent):
    """
    Reviews executor output and provides corrections.
    Implements a self-correction retry loop of up to MAX_RETRIES iterations.
    """

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools, role="critic")

    async def review(self, step: str, result: str) -> Tuple[bool, str]:
        """
        Review the result of executing a step.

        Returns:
            (is_valid: bool, final_result: str)
            If valid, final_result == original result.
            If invalid, final_result == critic's corrected version.
        """
        prompt = (
            f"STEP: {step}\n\n"
            f"RESULT TO REVIEW:\n{result}"
        )
        response = await self.think(prompt, system=CRITIC_SYSTEM)
        logger.info("[CriticAgent] Review response: %.120s…", response.replace('\n', ' '))

        if "VALID" in response and "NEEDS_IMPROVEMENT" not in response:
            return True, result

        # Extract corrected content
        if "CORRECTED:" in response:
            corrected = response.split("CORRECTED:", 1)[-1].strip()
            return False, corrected

        # Fallback: return critic's full response as correction
        return False, response

    async def review_with_retry(
        self,
        step: str,
        result: str,
        executor,
        context: str = "",
        publish=None,
        step_idx: int = 0,
    ) -> str:
        """
        Full retry loop: critic reviews → if invalid, re-runs executor → repeats.

        Args:
            step:     The task step description.
            result:   Initial executor result.
            executor: ExecutorAgent (or subclass) to re-run on failure.
            context:  Accumulated context from previous steps.
            publish:  SSE event publisher callable.
            step_idx: Step number for labelling trace events.

        Returns:
            Final (validated or best-effort) result string.
        """
        current_result = result

        for attempt in range(1, MAX_RETRIES + 1):
            is_valid, reviewed = await self.review(step, current_result)

            if publish:
                publish({
                    "type": "critic",
                    "agent": "critic",
                    "role": "critic",
                    "step": step_idx,
                    "attempt": attempt,
                    "status": "valid" if is_valid else "retry",
                    "content": (
                        f"✅ Step {step_idx + 1} validated on attempt {attempt}."
                        if is_valid
                        else f"⚠️ Attempt {attempt}: Issues found. Re-executing…"
                    ),
                })

            if is_valid:
                logger.info("[CriticAgent] Step %d VALID on attempt %d", step_idx, attempt)
                return reviewed

            # Not valid — use corrected text as new context and re-execute
            logger.warning("[CriticAgent] Step %d needs improvement (attempt %d)", step_idx, attempt)
            
            # AGENTIC SAFETY: If the error is a malformed request (400), do NOT retry.
            if "Bad Request (400)" in str(current_result) or "Invalid JSON" in str(current_result):
                logger.error("[CriticAgent] Malformed request detected. Aborting retries.")
                return current_result

            if attempt < MAX_RETRIES:
                # Feed critic's correction back into executor as guidance
                guided_step = f"{step}\n\nPrevious attempt was insufficient. Guidance: {reviewed}"
                current_result = await executor.execute(guided_step, context)
            else:
                logger.warning("[CriticAgent] Max retries reached for step %d. Using best result.", step_idx)
                current_result = reviewed  # Use critic's last corrected version

        return current_result
