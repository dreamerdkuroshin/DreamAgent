"""
backend/orchestrator/synthesizer.py

Response Synthesizer.
Merges partial results, ignores failed steps transparently,
and produces a clean final answer.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ResponseSynthesizer:
    async def synthesize(
        self,
        goal: str,
        step_results: List[Dict[str, Any]],  # [{"content": "...", "is_error": bool}, ...]
        context_block: str,
        llm: Any
    ) -> str:
        # Filter successful vs failed
        successful = [r for r in step_results if not r.get("is_error", False)]
        failed_count = len(step_results) - len(successful)

        if not successful:
            logger.warning("[Synthesizer] All steps failed. Returning fallback.")
            return "I was unable to complete this task. All steps encountered errors."

        partial_note = f"\n⚠️ Note: {failed_count} step(s) failed and were excluded." if failed_count > 0 else ""

        step_lines = "\n".join(f"- {r['content']}" for r in successful)
        
        prompt = f"""Goal: {goal}
Context: {context_block}
Completed steps:
{step_lines}
{partial_note}

Produce a clean, complete final answer based on the completed steps and context. Do not reference step numbers. Do not mention errors unless they are critical to the final answer."""
        
        try:
            final_answer = await llm.complete(prompt)
            return final_answer.strip()
        except Exception as e:
            logger.error(f"[Synthesizer] LLM synthesis failed: {e}")
            return "I completed some steps but encountered an error generating the final summary."

# Singleton
synthesizer = ResponseSynthesizer()
