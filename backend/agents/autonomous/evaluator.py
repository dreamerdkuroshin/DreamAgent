"""
backend/agents/autonomous/evaluator.py
Reflection mechanism deciding if the objective is complete.
"""
async def evaluate(provider, user_id: str, bot_id: str, goal: str, steps: list) -> str:
    prompt = f"""
Goal: {goal}

Steps executed:
{steps}

Did the agent complete the goal successfully?
Answer YES or NO strictly, then provide a 1 sentence reason.
"""
    return await provider.get_chat_completion(
        user_id=user_id,
        bot_id=bot_id,
        messages=[{"role": "user", "content": prompt}]
    )
