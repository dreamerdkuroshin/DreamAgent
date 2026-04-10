"""
backend/agents/autonomous/planner.py
Decomposes complex goals into JSON arrays of atomic exec steps.
"""
import json

async def create_plan(provider, user_id: str, bot_id: str, goal: str):
    # 🧠 Auto-Learning Component: Semantic Task Recall
    try:
        from backend.agents.autonomous.memory_engine import memory_engine
        similar_tasks = await memory_engine.retrieve_similar(bot_id=bot_id, goal=goal, k=3)
        context_str = ""
        if similar_tasks:
            context_str = "Past successful tasks and their plans (use them if relevant):\n"
            for t in similar_tasks:
                context_str += f"- Goal: {t['goal']}\n  Plan: {json.dumps(t['plan'])}\n"
    except Exception as e:
        context_str = ""
        print(f"[Planner] Memory recall skipped: {str(e)}")

    prompt = f"""
Break this goal into actionable steps.

[CONTEXT MEMORY]
{context_str}

Goal: {goal}

Rules:
- Each step must be executable.
- Mention tool if needed (e.g., "gmail_send", "notion_query", "sqlite_query", "google_drive").
- If no tool is required, omit the tool field or set to null.
- Keep steps minimal and explicit.

Return ONLY raw JSON in this format:
[
  {{ "action": "...", "tool": "optional_tool_name" }}
]
"""
    # Route securely through UniversalProvider mapped exactly to Bot's LLM model!
    res = await provider.get_chat_completion(
        user_id=user_id,
        bot_id=bot_id,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        # Strip code blocks if LLM surrounds it
        response_text = res.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        steps = json.loads(response_text)
        
        return [
            {"id": i, "action": s["action"], "tool": s.get("tool")}
            for i, s in enumerate(steps)
        ]
    except Exception as e:
        print(f"[Planner] Failed to parse plan JSON: {e}")
        return [{"id": 0, "action": goal, "tool": None}]
