"""
backend/orchestrator/autonomous.py

DreamAgent v2 Autonomous Controller
Runs a persistent goal loop (AutoGPT/BabyAGI style) instead of a single-pass workflow.
"""
import asyncio
import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

def _ts() -> str:
    """ISO-8601 timestamp string."""
    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).isoformat()


class AutonomousController:
    """
    Goal → Plan → Execute → Evaluate → Repeat → Finish
    """

    def __init__(self, planner_agent, executor_factory, critic_agent, memory_agent, max_iterations: int = 5):
        self.planner = planner_agent
        self.executor_factory = executor_factory  # callable(step) -> ExecutorAgent
        self.critic = critic_agent
        self.memory = memory_agent
        self.max_iterations = max_iterations

    async def run(self, goal: str, publish: Callable[[Dict[str, Any]], None]) -> str:
        logger.info(f"[GOAL] {goal}")
        
        publish({
            "type": "agent", "agent": "orchestrator", "role": "orchestrator",
            "status": "running", "timestamp": _ts(),
            "content": f"🚀 Initializing autonomous goal loop for: {goal[:100]}"
        })

        # Generate initial plan
        publish({
            "type": "plan", "agent": "planner", "role": "planner",
            "status": "running", "timestamp": _ts(),
            "content": "🧠 Planner composing initial execution strategy..."
        })
        
        plan_steps = await self.planner.plan(goal)
        
        publish({
            "type": "plan", "agent": "planner", "role": "planner",
            "status": "done", "timestamp": _ts(),
            "content": f"📋 Initial Plan — {len(plan_steps)} step(s):\n" +
                       "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan_steps))
        })

        # Load existing history if any (usually empty at start)
        history = await self.memory.load("history", [])

        for iteration in range(self.max_iterations):
            logger.info(f"\n[Iteration {iteration+1}/{self.max_iterations}]")
            
            # Rate limit mitigation: Cooldown between iterations
            if iteration > 0:
                await asyncio.sleep(1)

            publish({
                "type": "agent", "agent": "orchestrator", "role": "orchestrator",
                "status": "running", "timestamp": _ts(),
                "content": f"🔁 Starting Iteration {iteration+1}/{self.max_iterations}"
            })

            for step_idx, step in enumerate(plan_steps):
                if getattr(self, "_cancelled", False):
                    publish({"type": "error", "content": "Autonomous loop cancelled by user.", "timestamp": _ts()})
                    return "Task cancelled."

                # 1. Execute
                executor = self.executor_factory(step)
                context = await self._format_history(history)
                
                publish({
                    "type": "agent", "agent": executor.role, "role": executor.role,
                    "status": "running", "step": step_idx, "timestamp": _ts(),
                    "content": f"⚡ [{executor.role.upper()}] Executing: {step[:100]}"
                })
                
                result = await executor.execute(step, context)

                # 2. Critic Review with Retry
                review = await self._run_critic_loop(
                    step=step, 
                    result=result, 
                    executor=executor, 
                    context=context, 
                    publish=publish, 
                    step_idx=step_idx
                )

                # 3. Save to History/Memory
                step_record = {
                    "iteration": iteration + 1,
                    "step": step,
                    "result": review
                }
                history.append(step_record)
                
                # We could save to vector memory natively here
                await self.memory.append_step(len(history)-1, review)
                
                publish({
                    "type": "memory", "agent": "memory", "role": "memory",
                    "status": "saved", "step": step_idx, "timestamp": _ts(),
                    "content": f"🟣 Saved execution of '{step[:30]}...' to memory."
                })

            # 4. Evaluate Goal Completion
            publish({
                "type": "agent", "agent": "planner", "role": "planner",
                "status": "running", "timestamp": _ts(),
                "content": "🧠 Evaluating if the overarching goal is fully completed..."
            })
            
            done = await self.evaluate_goal(goal, history)

            if done:
                logger.info("[STATUS] Goal completed ✅")
                publish({
                    "type": "final", "agent": "orchestrator", "role": "orchestrator",
                    "status": "done", "timestamp": _ts(),
                    "content": f"✅ Goal achieved successfully in {iteration+1} iterations."
                })
                return self._finalize_output(history)

            if iteration < self.max_iterations - 1:
                # 5. Dynamic Replanning
                publish({
                    "type": "plan", "agent": "planner", "role": "planner",
                    "status": "running", "timestamp": _ts(),
                    "content": "🔁 Goal not fully met. Generating adapted sub-plan..."
                })
                
                plan_steps = await self.replan(goal, history)
                
                publish({
                    "type": "plan", "agent": "planner", "role": "planner",
                    "status": "done", "timestamp": _ts(),
                    "content": f"📋 Adapted Plan — {len(plan_steps)} step(s):\n" +
                               "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan_steps))
                })

        publish({
            "type": "final", "agent": "orchestrator", "role": "orchestrator",
            "status": "error", "timestamp": _ts(),
            "content": f"🛑 Stopped: Max iterations ({self.max_iterations}) reached before goal completion."
        })
        return self._finalize_output(history)

    async def _run_critic_loop(self, step: str, result: str, executor, context: str, publish: Callable, step_idx: int) -> str:
        """Critic loop up to 3 retries delegating to CriticAgent."""
        return await self.critic.review_with_retry(
            step=step,
            result=result,
            executor=executor,
            context=context,
            publish=publish,
            step_idx=step_idx
        )

    async def evaluate_goal(self, goal: str, history: List[Dict]) -> bool:
        """Determines if the overarching goal is met based on history."""
        hist_text = await self._format_history(history)
        prompt = f"""
        Goal: {goal}

        Progress so far:
        {hist_text}

        Has the overarching Goal been fully completed?
        Be analytical but decisive. If there is clearly more required work, say NO.
        If all explicit requirements of the Goal are met, say YES.
        Answer ONLY with a single word: YES or NO.
        """
        response = await self.planner.think(prompt, system="You are an autonomous progress evaluator.")
        return "YES" in str(response).upper()

    async def replan(self, goal: str, history: List[Dict]) -> List[str]:
        """Generates a new plan based on missing requirements."""
        hist_text = await self._format_history(history)
        prompt = f"""
        Overarching Goal: {goal}

        Completed Iteration Steps:
        {hist_text}

        The goal is NOT yet complete. What must be done NEXT to get closer to the goal?
        Generate a strictly numbered list of actionable steps.
        Make steps CLEAR, ACTIONABLE, and NON-REPEATING from previous history.
        Do NOT output markdown outside of the numbered list. Limit to 3-5 steps max.
        """
        response = await self.planner.think(prompt, system="You are an autonomous dynamic replanner.")
        response = str(response)
        
        # Filter and extract numbered steps
        steps = []
        for line in response.split("\n"):
            line = line.strip()
            if line and line[0].isdigit() and "." in line[:3]:
                step_text = line.split(".", 1)[1].strip()
                steps.append(step_text)
        
        # Fallback if parsing fails
        if not steps:
            steps = [response.strip()]
            
        return steps[:5]

    async def think_step(self, goal: str, history: List[Dict]) -> str:
        """Agent reflection before acting (Optional standard think)."""
        hist_text = await self._format_history(history)
        prompt = f"""
        Goal: {goal}

        Current progress:
        {hist_text}

        What is the BEST next autonomous action? Explain your reasoning briefly.
        """
        return await self.planner.think(prompt)

    async def _format_history(self, history: List[Dict]) -> str:
        """Helper to format python dict history into string context."""
        if not history:
            return "No previous steps completed."
        
        out = []
        for h in history:
            out.append(f"Iter {h.get('iteration', '?')} | Step: {h['step']}\nOutput: {h['result'][:200]}...")
        return "\n\n".join(out)

    def _finalize_output(self, history: List[Dict]) -> str:
        """Formats the final payload for the user after loop termination."""
        if not history:
            return "Autonomous loop finished with no steps."
        
        # Omit execution summary and just return the last result as the final answer
        # The user only wants the final outcome, not the trace.
        last_step = history[-1]
        return last_step.get('result', "Action completed successfully.")
