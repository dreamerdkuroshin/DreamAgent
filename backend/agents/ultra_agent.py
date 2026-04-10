"""
backend/agents/ultra_agent.py
The main multi-step autonomous agent orchestrator (UltraAgent).
Includes MAX_STEPS and timeout safety guards.
"""
import asyncio
import logging
import time
from typing import Any, Callable, Dict, Optional
from backend.llm.universal_provider import UniversalProvider

logger = logging.getLogger(__name__)

MAX_STEPS_COMPLEX = 10  # full autonomous mode
MAX_STEPS_SIMPLE  = 3   # simple tasks that slipped through
STEP_TIMEOUT = 60  # seconds per step


class UltraAgent:
    """
    A safe, constrained autonomous agent:
    - Max steps enforced
    - Per-step timeout
    - Graceful cancellation support
    - LLM provider fallback
    """
    def __init__(self, provider: str = "auto", model: str = "", max_steps: int = MAX_STEPS_COMPLEX):
        self.provider_name = provider
        self.model = model
        self.max_steps = max_steps
        self._cancelled = False
        # Expose llm immediately so chat_worker can read final_provider/final_model
        self.llm = UniversalProvider(provider=provider, model=model)

    def cancel(self):
        self._cancelled = True

    def _clean_output(self, text: str) -> str:
        """Removes annoying LLM boilerplate phrases."""
        blacklist = [
            "As an AI,",
            "As an AI assistant,",
            "As a language model,",
            "I am a backend AI",
            "I can't",
            "I cannot",
            "I do not have the ability",
            "Here is the final answer:",
            "Here is the response:"
        ]
        for phrase in blacklist:
            text = text.replace(phrase, "")
        return text.strip()

    async def run(
        self,
        goal: str,
        publish: Callable[[Dict[str, Any]], None],
        check_cancelled: Optional[Callable[[], bool]] = None,
        stream_tokens: bool = True,
    ) -> str:
        from datetime import datetime, timezone

        def _ts():
            return datetime.now(tz=timezone.utc).isoformat()

        def _pub(event: Dict[str, Any]):
            try:
                publish(event)
            except Exception:
                pass

        _pub({
            "type": "agent", "agent": "ultra_agent", "role": "orchestrator",
            "status": "running", "timestamp": _ts(),
            "content": f"🚀 UltraAgent starting: {goal[:120]}"
        })

        llm = self.llm  # already initialized in __init__
        history = []

        for step in range(self.max_steps):
            # Check cancellation
            if self._cancelled or (check_cancelled and check_cancelled()):
                _pub({"type": "error", "content": "Task cancelled.", "timestamp": _ts()})
                return "Task cancelled by user."

            context = "\n".join(
                f"Step {i+1}: {h['thought']} → {str(h.get('result',''))[:300]}"
                for i, h in enumerate(history)
            ) or "No previous steps."

            think_prompt = (
                f"Goal: {goal}\n\n"
                f"Progress:\n{context}\n\n"
                f"Step {step+1}/{self.max_steps}: What is the single best next action?\n"
                "If you already know the answer or the last step returned it, reply with exactly: FINISH\n"
                "If you can answer right now without tools, reply with: FINAL ANSWER: [your complete answer]\n"
                "Otherwise reply with the next concrete action in one sentence."
            )

            _pub({
                "type": "thinking", "agent": "ultra_agent", "role": "planner",
                "status": "running", "step": step, "timestamp": _ts(),
                "content": f"🧠 Planning step {step+1}/{MAX_STEPS}..."
            })

            try:
                thought = await asyncio.wait_for(
                    llm.complete(think_prompt),
                    timeout=STEP_TIMEOUT
                )
            except asyncio.TimeoutError:
                _pub({"type": "error", "content": f"Step {step+1} timed out.", "timestamp": _ts()})
                break
            except Exception as e:
                _pub({"type": "error", "content": f"LLM error: {str(e)}", "timestamp": _ts()})
                break

            thought = str(thought).strip()

            if "FINISH" in thought.upper() or "FINAL ANSWER:" in thought.upper():
                _pub({
                    "type": "final", "agent": "ultra_agent", "role": "orchestrator",
                    "status": "done", "timestamp": _ts(),
                    "content": f"✅ Goal achieved in {step+1} steps."
                })
                break

            _pub({
                "type": "step", "agent": "ultra_agent", "role": "executor",
                "status": "running", "step": step, "timestamp": _ts(),
                "content": f"⚡ Action: {thought[:200]}"
            })

            # Execute thought as action
            try:
                result = await asyncio.wait_for(
                    llm.complete(f"Execute this action and return the result:\n{thought}"),
                    timeout=STEP_TIMEOUT
                )
                result = str(result).strip()
            except asyncio.TimeoutError:
                result = "Action timed out."
            except Exception as e:
                result = f"Action failed: {str(e)}"

            history.append({"thought": thought, "result": result})

            _pub({
                "type": "result", "agent": "ultra_agent", "role": "executor",
                "status": "done", "step": step, "timestamp": _ts(),
                "content": f"📦 Result: {result[:300]}"
            })

            # Early exit if the execution result itself is the final answer
            if "final answer:" in result.lower() or "final answer is" in result.lower() or "goal achieved" in result.lower():
                break

        if not history:
            return "No concrete action was taken."

        # Build final synthesis prompt
        from backend.core.persona_engine import get_persona_prompt
        persona = get_persona_prompt(goal, is_autonomous=True)
        
        context_str = "\n".join(f"- {h['thought']}:\n  {h.get('result', '')}" for h in history)
        final_prompt = (
            f"{persona}\n\n"
            f"Original Request: {goal}\n\n"
            "INTERNAL LOGS (Hidden from user):\n"
            f"{context_str}\n\n"
            "Based ONLY on the internal logs above, provide the clean, final, direct answer to the user's original request.\n"
            "Rules:\n"
            "- Give a clear, direct answer matching the persona.\n"
            "- Do NOT show steps, logs, or your thinking process.\n"
            "- Speak naturally according to your mode.\n"
            "- Just provide the final answer immediately."
        )

        # ── Token streaming (ChatGPT-style) ──────────────────────────────────────
        if stream_tokens:
            try:
                accumulated = ""
                messages = [{"role": "user", "content": final_prompt}]

                # Consume the true async generator directly
                async for token in llm.astream(messages):
                    if token and not token.startswith("Error:"):
                        accumulated += token
                        _pub({"type": "token", "content": token})

                if accumulated:
                    return self._clean_output(accumulated)
            except Exception as e:
                logger.warning(f"[UltraAgent] Token streaming failed, falling back to complete(): {e}")

        # ── Fallback: single complete() call ─────────────────────────────────────
        try:
            final_answer = await asyncio.wait_for(
                llm.complete(final_prompt),
                timeout=STEP_TIMEOUT
            )
            final_answer = str(final_answer).strip()

            # Emit as tokens for consistent frontend experience
            if stream_tokens and final_answer:
                chunk_size = 6  # emit ~6 chars at a time
                for i in range(0, len(final_answer), chunk_size):
                    chunk = final_answer[i:i + chunk_size]
                    _pub({"type": "token", "content": chunk})
                    await asyncio.sleep(0.01)  # 10ms delay for typing feel
        except Exception:
            final_answer = history[-1].get("result") or "Action completed."

        return self._clean_output(final_answer)
