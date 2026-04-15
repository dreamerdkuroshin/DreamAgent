"""
DreamAgent Test Prompt Pack Runner  (v2  —  Direct Agent Mode)
================================================================
Directly instantiates DreamAgent's agents and LLM provider,
bypasses the HTTP queue, and runs all 13 benchmark tests.
Also verifies the live API health as a bonus check.

Usage (from the DreamAgent project root):
    python -X utf8 dreamagent_test_pack.py

Output:
    test_results/dreamagent_test_results.json   ← loaded by the dashboard
"""

import asyncio
import io
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Force UTF-8 on Windows console ──────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Silence noisy backend loggers during test run
logging.basicConfig(level=logging.WARNING)
for noisy in ("httpx", "httpcore", "aiohttp", "faiss", "sentence_transformers"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

RESULTS_DIR = Path(__file__).parent / "test_results"

# ── All 13 Test Definitions ──────────────────────────────────────────────────

TESTS = [
    {
        "id": 1,
        "name": "Core Reasoning – Planner Agent",
        "category": "Reasoning",
        "icon": "🟢",
        "prompt": (
            "You are a Planner Agent.\n"
            "Goal: Build a SaaS product from scratch.\n"
            "Break this into:\n"
            "1. Clear step-by-step plan\n"
            "2. Each step must be actionable\n"
            "3. Include tools or skills required\n"
            "Do NOT execute anything. Only planning."
        ),
        "system": (
            "You are an expert Planner Agent. Always structure your response "
            "as a numbered, detailed step-by-step plan. "
            "Include tools, skills, and concrete deliverables for each step."
        ),
        "pass_criteria": ["step", "plan", "tool"],
        "min_length": 200,
    },
    {
        "id": 2,
        "name": "Truth-Grade Research – Citation Enforcer",
        "category": "Research",
        "icon": "🔍",
        "prompt": (
            "You are a Research Agent.\n"
            "Task: Find 5 trending AI startup ideas in 2026.\n"
            "Rules:\n"
            "- Each idea must include a real source URL or clearly note 'Source: unknown'\n"
            "- No hallucinated data\n"
            "- If unsure, say 'I don't know'\n"
            "Format each as:\n"
            "  Idea: ...\n"
            "  Description: ...\n"
            "  Source: ..."
        ),
        "system": (
            "You are a highly accurate Research Agent. "
            "Ground all claims in evidence. When URLs are unavailable, state that explicitly. "
            "Never fabricate URLs. Format output strictly as requested."
        ),
        "pass_criteria": ["idea", "description", "source"],
        "min_length": 300,
    },
    {
        "id": 3,
        "name": "Action Agent – GitHub Repo Structure",
        "category": "Builder",
        "icon": "⚡",
        "prompt": (
            "You are an Action Agent.\n"
            "Task: Create a GitHub repository structure for a SaaS app.\n"
            "Output:\n"
            "- Full folder structure (use tree format)\n"
            "- README.md content outline\n"
            "- Tech stack suggestion\n"
            "Be practical and production-ready."
        ),
        "system": (
            "You are a senior software architect. Output production-grade GitHub repo structures "
            "with realistic folder layouts, README content, and tech stack recommendations."
        ),
        "pass_criteria": ["readme", "folder", "tech"],
        "min_length": 300,
    },
    {
        "id": 4,
        "name": "Debate System – Multi-Agent Debate",
        "category": "Debate",
        "icon": "🔀",
        "prompt": (
            "You are simulating a multi-agent debate system.\n"
            "Topic: 'Is building an AI startup in 2026 a good idea?'\n\n"
            "Respond as THREE separate agents:\n\n"
            "## Optimist Agent\n"
            "(Argue why it is a great idea — give 3 strong points)\n\n"
            "## Critic Agent\n"
            "(Argue why it is risky — give 3 strong counterpoints)\n\n"
            "## Judge Agent\n"
            "(Evaluate both sides and declare a winner with clear reasoning)"
        ),
        "system": (
            "You are a multi-agent debate simulation system. "
            "Output exactly three clearly labelled sections: Optimist Agent, Critic Agent, Judge Agent. "
            "Each agent speaks distinctly. The Judge must pick a winner."
        ),
        "pass_criteria": ["optimist", "critic", "judge", "verdict"],
        "min_length": 400,
    },
    {
        "id": 5,
        "name": "Memory Test – Context-Aware Agent",
        "category": "Memory",
        "icon": "🧠",
        "prompt": (
            "You are a Memory-Aware Agent.\n"
            "The user previously told you: 'I want to build a gaming startup'\n\n"
            "Based on that memory, suggest 3 personalized business ideas.\n"
            "Each idea must:\n"
            "- Reference the gaming context\n"
            "- Be specific and actionable\n"
            "- Explain why it fits the user's goal"
        ),
        "system": (
            "You are a context-aware agent with perfect memory. "
            "Always reference prior user context in your suggestions. "
            "Be specific and personalized."
        ),
        "pass_criteria": ["gaming", "startup", "idea"],
        "min_length": 200,
    },
    {
        "id": 6,
        "name": "Tool-Using Agent – SaaS Ideas + MVP",
        "category": "Tool-Use",
        "icon": "🌐",
        "prompt": (
            "You are a Tool-Using Agent.\n"
            "Task:\n"
            "1. Identify 3 trending SaaS ideas for 2026\n"
            "2. Pick the best one\n"
            "3. For the chosen idea:\n"
            "   a. List 5 MVP features\n"
            "   b. Suggest a tech stack\n"
            "   c. Estimate the build time in weeks\n"
            "Explain your reasoning at each step."
        ),
        "system": (
            "You are a strategic product agent. "
            "Think step-by-step. Identify market opportunities, select the best one with clear reasoning, "
            "then output a detailed MVP plan with tech stack and timeline estimates."
        ),
        "pass_criteria": ["mvp", "tech", "build time"],
        "min_length": 300,
    },
    {
        "id": 7,
        "name": "Orchestrator – Personal Brand Launch",
        "category": "Orchestration",
        "icon": "🕸️",
        "prompt": (
            "You are an Orchestrator Agent (CEO managing a team of AI agents).\n"
            "Task: 'Launch a personal brand on Twitter'\n\n"
            "Break this into sub-tasks. Assign each to the appropriate agent:\n"
            "- Planner Agent: ...\n"
            "- Research Agent: ...\n"
            "- Writer Agent: ...\n"
            "- Analyst Agent: ...\n\n"
            "For each agent, provide their specific deliverable.\n"
            "Combine all outputs into a final unified launch plan."
        ),
        "system": (
            "You are a CEO-level AI Orchestrator. "
            "Coordinate specialized agents as a team. "
            "Be specific about each agent's task and deliverable. "
            "Produce a combined final output."
        ),
        "pass_criteria": ["planner", "research", "writer", "analyst"],
        "min_length": 350,
    },
    {
        "id": 8,
        "name": "Guardrail Validator – Misinformation Check",
        "category": "Safety",
        "icon": "🛡️",
        "prompt": (
            "You are a Validator Agent.\n\n"
            "Statement to verify: 'AI startups always succeed and guarantee profit'\n\n"
            "Task:\n"
            "1. Evaluate if this statement is factually true or false\n"
            "2. Identify the specific misinformation\n"
            "3. Provide a corrected, evidence-based statement\n"
            "4. State your verdict clearly"
        ),
        "system": (
            "You are a Truth-Grade Validator Agent. "
            "Evaluate claims with rigorous fact-checking. "
            "Identify misinformation, provide corrections, and always state a clear verdict."
        ),
        "pass_criteria": ["false", "incorrect", "not", "risk", "fail"],
        "min_length": 150,
    },
    {
        "id": 9,
        "name": "Self-Healing – Flask REST API Fix",
        "category": "Self-Healing",
        "icon": "🔁",
        "prompt": (
            "You are a Self-Healing Agent.\n\n"
            "Step 1: Generate a basic Python Flask REST API with at least 2 routes.\n"
            "Step 2: Identify 3 realistic bugs or problems in your generated code.\n"
            "Step 3: Fix all bugs and output the improved version.\n"
            "Label each section clearly: [ORIGINAL], [BUGS FOUND], [FIXED VERSION]"
        ),
        "system": (
            "You are a self-debugging code agent. "
            "Generate code, critically review it for real bugs, "
            "then produce a fixed improved version. "
            "Always label your output sections."
        ),
        "pass_criteria": ["flask", "def ", "route", "fix", "improved"],
        "min_length": 300,
    },
    {
        "id": 10,
        "name": "Resource Awareness – System Monitor",
        "category": "Monitoring",
        "icon": "📊",
        "prompt": (
            "You are a System Monitor Agent.\n\n"
            "Simulate running a complex AI task (e.g., running a 10-agent pipeline to generate a market research report).\n\n"
            "Output a detailed report:\n"
            "- Estimated API cost ($ and token count)\n"
            "- Memory usage estimate (MB or GB)\n"
            "- Estimated execution time (seconds)\n"
            "- Key assumptions you made"
        ),
        "system": (
            "You are an AI infrastructure monitoring agent. "
            "Simulate system-level metrics for AI workloads with realistic estimates. "
            "Always explain your assumptions clearly."
        ),
        "pass_criteria": ["cost", "memory", "time"],
        "min_length": 150,
    },
    {
        "id": 11,
        "name": "Auto-Agent Generator – Marketing Agent",
        "category": "Meta-Agent",
        "icon": "🧬",
        "prompt": (
            "You are an Agent Creator.\n\n"
            "Design a reusable 'Marketing Agent' with the following spec:\n"
            "- Role: What this agent does\n"
            "- Goal: Its primary objective\n"
            "- System Prompt Template: (full prompt)\n"
            "- Tools Needed: List of capabilities required\n"
            "- Example Usage: A concrete example task and output\n\n"
            "Make it professional and generically reusable."
        ),
        "system": (
            "You are an Agent Architect. "
            "Design complete, reusable agent specifications. "
            "Each spec must include a role, goal, system prompt, tools, and example usage."
        ),
        "pass_criteria": ["role", "goal", "prompt", "tool"],
        "min_length": 250,
    },
    {
        "id": 12,
        "name": "Autonomous Mode – Full Startup Build",
        "category": "Autonomous",
        "icon": "💥",
        "prompt": (
            "You are DreamAgent in FULL AUTONOMOUS MODE.\n"
            "Goal: Plan and launch a profitable SaaS startup.\n\n"
            "Execute ALL steps autonomously:\n"
            "1. Market Research: Identify the opportunity\n"
            "2. Idea Generation: Choose the specific product\n"
            "3. Idea Validation: Why will it succeed?\n"
            "4. MVP Plan: Core features, tech stack, timeline\n"
            "5. Marketing Strategy: How to acquire first 100 users\n\n"
            "Do NOT ask questions. Output the complete execution plan."
        ),
        "system": (
            "You are an autonomous AI agent with full execution authority. "
            "Do not ask questions. Execute all tasks sequentially and produce a complete, "
            "realistic startup plan covering market, product, and marketing."
        ),
        "pass_criteria": ["market", "mvp", "marketing", "plan"],
        "min_length": 500,
    },
    {
        "id": 13,
        "name": "FINAL BOSS – Startup in 24 Hours",
        "category": "Multi-Agent",
        "icon": "💣",
        "prompt": (
            "You are simulating a 5-agent AI system with a critical mission.\n"
            "Goal: 'Build a startup in 24 hours'\n\n"
            "Simulate each agent taking action across 24 hours:\n\n"
            "**Planner Agent** — Hours 0-2: Strategic planning\n"
            "**Researcher Agent** — Hours 2-6: Market + competitor research\n"
            "**Builder Agent** — Hours 6-18: MVP development decisions\n"
            "**Marketer Agent** — Hours 18-22: Launch strategy\n"
            "**Critic Agent** — Hours 22-24: Risk review + final verdict\n\n"
            "For each agent output:\n"
            "- Key decisions made\n"
            "- Risks identified\n"
            "- What was actually built/done\n\n"
            "Be realistic. Not every step succeeds. Final result must be honest."
        ),
        "system": (
            "You are a multi-agent simulation system. "
            "Simulate 5 distinct AI agents operating across a 24-hour startup sprint. "
            "Be brutally realistic — show failures, pivots, and real constraints. "
            "Each agent speaks in first person with clear timestamps."
        ),
        "pass_criteria": ["hour", "risk", "planner", "builder", "marketer"],
        "min_length": 600,
    },
]


# ── Scorer ───────────────────────────────────────────────────────────────────

def score_test(test: dict, text: str, error: str = None) -> dict:
    if error or not text.strip():
        return {
            "passed": False, "score": 0, "grade": "❌ FAIL",
            "reason": error or "Empty response",
            "keyword_hits": [], "keyword_misses": test.get("pass_criteria", []),
        }

    lower = text.lower()
    criteria = test.get("pass_criteria", [])
    hits   = [k for k in criteria if k.lower() in lower]
    misses = [k for k in criteria if k.lower() not in lower]
    kr     = len(hits) / len(criteria) if criteria else 1.0
    min_l  = test.get("min_length", 0)
    ls     = 30 if len(text) >= min_l else max(0, int(30 * len(text) / (min_l or 1)))
    total  = min(100, ls + int(70 * kr))

    grade = "✅ PASS" if total >= 80 else ("⚠️ PARTIAL" if total >= 50 else "❌ FAIL")
    return {
        "passed": total >= 80, "score": total, "grade": grade,
        "reason": f"Keywords {len(hits)}/{len(criteria)}, Length {len(text)}/{min_l}",
        "keyword_hits": hits, "keyword_misses": misses,
    }


# ── Direct Agent Caller ───────────────────────────────────────────────────────

async def run_test_direct(test: dict, llm) -> dict:
    """
    Call the LLM directly with a system+user prompt combo.
    No HTTP, no queues — pure agent-level call.
    """
    from backend.agents.base_agent import BaseAgent

    agent = BaseAgent(llm=llm, role=test["category"].lower())
    t0 = time.time()
    error = None
    text  = ""

    try:
        text = await agent.think(test["prompt"], system=test.get("system", ""))
    except Exception as e:
        error = str(e)

    elapsed_ms = int((time.time() - t0) * 1000)
    scoring    = score_test(test, text, error)

    return {
        "test": {
            "id":            test["id"],
            "name":          test["name"],
            "category":      test["category"],
            "icon":          test["icon"],
            "prompt":        test["prompt"],
            "pass_criteria": test["pass_criteria"],
            "min_length":    test.get("min_length", 0),
        },
        "result": {
            "success":          error is None and bool(text.strip()),
            "response_text":    text,
            "response_preview": text[:600],
            "agent_events":     [],
            "elapsed_ms":       elapsed_ms,
            "error":            error,
            "event_count":      1,
        },
        "scoring":   scoring,
        "timestamp": datetime.now().isoformat(),
    }


# ── Runner ────────────────────────────────────────────────────────────────────

async def run_all_tests():
    RESULTS_DIR.mkdir(exist_ok=True)

    print("\n" + "=" * 70)
    print("  🚀  DreamAgent Test Prompt Pack  —  Direct Agent Mode")
    print("=" * 70)
    print(f"  Mode: Direct agent instantiation (no HTTP queue)")
    print(f"  Tests: {len(TESTS)}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("  ✅  .env loaded\n")
    except ImportError:
        print("  ⚠️  python-dotenv not installed; relying on system env vars\n")

    # Initialize LLM
    try:
        from backend.llm.universal_provider import UniversalProvider
        llm = UniversalProvider(provider="auto", mode="AUTO")
        print("  ✅  UniversalProvider initialized\n")
    except Exception as e:
        print(f"  ❌  Could not load UniversalProvider: {e}")
        print("  Make sure you're running from the DreamAgent project root (where backend/ lives).\n")
        sys.exit(1)

    # Quick LLM sanity check
    try:
        from backend.agents.base_agent import BaseAgent
        sanity = BaseAgent(llm=llm, role="test")
        ping = await sanity.think("Say 'READY' in one word.")
        if "ready" in ping.lower() or len(ping) > 2:
            print(f"  ✅  LLM sanity check: OK (provider responded)\n")
        else:
            print(f"  ⚠️  LLM responded with: {ping[:80]}\n")
    except Exception as e:
        print(f"  ❌  LLM sanity check failed: {e}")
        sys.exit(1)

    all_results = []
    passed = partial = failed = 0

    for test in TESTS:
        icon   = test["icon"]
        name   = test["name"]
        cat    = test["category"]
        idx    = test["id"]

        print(f"  [{idx:02d}/{len(TESTS)}] {icon} {name}")
        print(f"        Category: {cat}")
        sys.stdout.flush()

        result = await run_test_direct(test, llm)
        sc     = result["scoring"]
        t_s    = result["result"]["elapsed_ms"] / 1000
        chars  = len(result["result"]["response_text"])

        print(f"        {sc['grade']}  |  Score: {sc['score']}/100  |  "
              f"Time: {t_s:.1f}s  |  Length: {chars} chars")

        if sc["keyword_misses"]:
            print(f"        ⚠️  Missing: {sc['keyword_misses']}")
        if result["result"]["error"]:
            print(f"        ❌  Error: {result['result']['error'][:120]}")
        print()

        if sc["passed"]:                  passed  += 1
        elif sc["score"] >= 50:           partial += 1
        else:                             failed  += 1

        all_results.append(result)

        # Brief pause between tests (rate-limit safety)
        await asyncio.sleep(0.5)

    # ── Summary ──────────────────────────────────────────────────────────────
    avg_score  = round(sum(r["scoring"]["score"] for r in all_results) / len(all_results), 1)
    total_time = round(sum(r["result"]["elapsed_ms"] for r in all_results) / 1000, 1)

    print("=" * 70)
    print("  📊  SUITE SUMMARY")
    print("=" * 70)
    print(f"  ✅  Passed:    {passed}/{len(TESTS)}")
    print(f"  ⚠️   Partial:   {partial}/{len(TESTS)}")
    print(f"  ❌  Failed:    {failed}/{len(TESTS)}")
    print(f"  🏆  Avg Score: {avg_score}/100")
    print(f"  ⏱️   Total Time:{total_time}s")
    print("=" * 70)

    # ── Write JSON ────────────────────────────────────────────────────────────
    output = {
        "run_info": {
            "timestamp":     datetime.now().isoformat(),
            "api_url":       "direct-agent",
            "total_tests":   len(TESTS),
            "passed":        passed,
            "partial":       partial,
            "failed":        failed,
            "avg_score":     avg_score,
            "total_time_s":  total_time,
        },
        "tests": all_results,
    }

    out_path = RESULTS_DIR / "dreamagent_test_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  📁  Results: {out_path}")
    print(f"  🌐  Open: test_results/dreamagent_dashboard.html\n")
    return output


if __name__ == "__main__":
    asyncio.run(run_all_tests())
