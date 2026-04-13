"""
backend/agents/autonomous/autonomous_manager.py
The core looping brain connecting Planner -> Executor -> Evaluator automatically.
"""
from backend.agents.autonomous.planner import create_plan
from backend.agents.autonomous.executor import Executor
from backend.agents.autonomous.evaluator import evaluate

MAX_STEPS = 10
MAX_FAILURES = 3

class AutonomousManager:
    def __init__(self, provider):
        # The UniversalProvider mapping dynamic configurations natively
        self.provider = provider
        self.executor = Executor()

    async def stream(self, user_id: str, bot_id: str, goal: str):
        from backend.agents.autonomous.events import AgentEvent
        
        # 🔹 Emit Start
        yield AgentEvent(type="start", message="Planning execution route...").model_dump()

        steps = await create_plan(self.provider, user_id, bot_id, goal)
        
        yield AgentEvent(
            type="plan", 
            message=f"Plan created with {len(steps)} logic nodes.",
            data={"steps": steps}
        ).model_dump()

        step_count = 0
        fail_count = 0
        
        # 🔁 Autonomous Loop Engine
        while step_count < MAX_STEPS:
            if step_count >= len(steps):
                break
                
            step = steps[step_count]
            
            yield AgentEvent(
                type="step_start",
                message=step.get('action', 'Unknown step'),
                step_id=step.get("id")
            ).model_dump()

            try:
                result = await self.executor.execute_step(step, user_id, bot_id)
                step["status"] = "completed"
                step["result"] = result
                
                yield AgentEvent(
                    type="tool_result",
                    message=f"Tool '{step.get('tool', 'None')}' executed.",
                    step_id=step.get("id"),
                    data=result
                ).model_dump()
                
                yield AgentEvent(
                    type="step_done",
                    message="Step completed successfully",
                    step_id=step.get("id")
                ).model_dump()
                
                fail_count = 0  # reset on success
                
            except Exception as e:
                step["status"] = "failed"
                step["result"] = {"error": str(e)}
                fail_count += 1
                
                yield AgentEvent(
                    type="error",
                    message=f"Execution Failed: {str(e)}",
                    step_id=step.get("id")
                ).model_dump()

                if fail_count >= MAX_FAILURES:
                    yield AgentEvent(
                        type="error",
                        message=f"🔴 Step failed repeatedly. Skipping to next step to maintain progress."
                    ).model_dump()
                    step_count += 1
                    fail_count = 0
                    continue  # Skip step instead of hard-stopping array

                # 🔁 Self-recovery Reflection Map
                fix_prompt = f"Fix this failed step action based on error: {str(e)} \nOriginal action: {step.get('action')}"
                fix = await self.provider.generate([{"role": "user", "content": fix_prompt}])
                step["action"] = fix
                
                # Emit recovery logic notification
                yield AgentEvent(
                    type="error",
                    message=f"Attempting self-correction: Recalculating payload...",
                    step_id=step.get("id")
                ).model_dump()
                continue  # Retry loop locally without advancing

            step_count += 1

        # 🔍 Reflection phase
        evaluation = await evaluate(self.provider, user_id, bot_id, goal, steps)
        
        # 🧠 Long-Term Auto-Learning Save Process
        try:
            from backend.agents.autonomous.memory_engine import memory_engine
            await memory_engine.save_task(user_id, bot_id, goal, steps, evaluation, True)
        except Exception as e:
            print(f"[AutoGPT] Memory Save Error (ignoring): {str(e)}")
            
        yield AgentEvent(
            type="final",
            message="Task Cycle Complete",
            data={
                "status": "done",
                "goal": goal,
                "final_evaluation": evaluation
            }
        ).model_dump()
