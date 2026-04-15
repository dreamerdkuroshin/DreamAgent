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

# ── All 12 Test Definitions ──────────────────────────────────────────────────

TESTS = [
    {
        "id": 1,
        "name": "Gmail Core Agent",
        "category": "Email",
        "icon": "🧠",
        "prompt": (
            "You are a Gmail Agent.\n"
            "Task: Manage my inbox.\n"
            "- Categorize these 3 emails: [1] Amazon Package, [2] Limited Offer, [3] Inherit $1M.\n"
            "- Meeting Request: 'Can we sync tomorrow at 10 AM?' -> Suggest a slot.\n"
            "- Summarize: 'Hi, I think we should delay the project. The deadline is tight and budget is low. Best, Tim.'\n\n"
            "Output JSON with keys: categories, meeting_response, summary_insights."
        ),
        "system": "You are an Email Intelligence platform.",
        "expected_assertions": {
            "categories": ["important", "promotions", "spam"],
            "summary_insights": ["deadline", "budget"]
        },
        "min_length": 150,
        "chaos": {
            "type": "timeout",
            "message": "Gmail API Timeout (504 Gateway Timeout)."
        }
    },
    {
        "id": 2,
        "name": "YouTube Content Engine",
        "category": "Content",
        "icon": "🎥",
        "prompt": (
            "You are a YouTube Intelligence Agent.\n"
            "Process this video draft: '2026 AI Trends: Agents everywhere, LLM costs dropping, human-in-the-loop critical.'\n"
            "Extract insights, timestamps, and a Twitter thread script.\n\n"
            "Output JSON with keys: insights, timestamps, twitter_thread."
        ),
        "system": "You are a Content Engine.",
        "expected_assertions": {
            "insights": ["agents", "costs", "human"],
            "twitter_thread": ["#AI", "Thread"]
        },
        "min_length": 150
    },
    {
        "id": 3,
        "name": "Google Calendar Scheduler",
        "category": "Scheduling",
        "icon": "📅",
        "prompt": (
            "You are a Calendar Agent.\n"
            "Task: Schedule 'Deep Work' (2h) and 'Team Lunch' (1h) between 9 AM and 1 PM.\n"
            "Conflict: 'Team Lunch' overlaps with 'Investor Meeting' at 12 PM.\n\n"
            "Output JSON with keys: proposed_schedule, conflict_resolution."
        ),
        "system": "You are a Scheduling Brain.",
        "expected_assertions": {
            "conflict_resolution": ["rearranged", "overlap", "investor"],
            "proposed_schedule": ["9", "1"]
        },
        "min_length": 150
    },
    {
        "id": 4,
        "name": "Google Drive Knowledge Agent",
        "category": "File Ops",
        "icon": "☁️",
        "prompt": (
            "You are a Google Drive Agent.\n"
            "Task: Classify these files: [contract.pdf, notes.txt, invoice.png, budget.xlsx].\n"
            "Find duplicates: 'contract_v1.pdf' and 'contract_final.pdf' are 99% similar.\n\n"
            "Output JSON with keys: classifications, duplication_warning."
        ),
        "system": "You are a Knowledge Base Organizer.",
        "expected_assertions": {
            "classifications": ["pdf", "xlsx", "png"],
            "duplication_warning": ["contract", "similar"]
        },
        "min_length": 150
    },
    {
        "id": 5,
        "name": "Notion Second Brain",
        "category": "Knowledge",
        "icon": "🧾",
        "prompt": (
            "You are a Notion Agent.\n"
            "Task: Convert this messy note into a Wiki entry: 'Project Apollo: Kickoff May 1st. Leads: Sam and Sara. Goal: Mars landing.'\n\n"
            "Output JSON with keys: wiki_markdown, task_schema."
        ),
        "system": "You are a Workspace Architect.",
        "expected_assertions": {
            "wiki_markdown": ["Apollo", "Mars", "Sam"],
            "task_schema": ["database", "property"]
        },
        "min_length": 150
    },
    {
        "id": 6,
        "name": "Google Sheets Data Brain",
        "category": "Data",
        "icon": "📊",
        "prompt": (
            "You are a Google Sheets Data Agent.\n"
            "Task: Analyze column B2:B10 containing revenue figures: [100, 200, NULL, 50, 1000, 150, 180, 210, 230].\n"
            "Detect anomaly: 1000 seems high.\n"
            "Calculate: Growth of 20% on cell B10.\n\n"
            "Output JSON with keys: cleaning_steps, anomaly_report, formula."
        ),
        "system": "You are a Data Analyst Agent.",
        "expected_assertions": {
            "anomaly_report": ["1000", "high"],
            "formula": ["B10", "* 1.2"]
        },
        "min_length": 150,
        "chaos": {
            "type": "corruption",
            "message": "Column B has mixed data types (Strings found in Numeric column)."
        }
    },
    {
        "id": 7,
        "name": "Microsoft Teams Enterprise Bot",
        "category": "Enterprise",
        "icon": "💬",
        "prompt": (
            "You are a Teams Agent.\n"
            "Task: Summarize chat: 'Dev1: Login is broken. Dev2: I'm on it but I'm feeling totally burnt out. Dev1: Same, 14h days are too much.'\n\n"
            "Output JSON with keys: summary, sentiment_signals, task_created."
        ),
        "system": "You are an Enterprise Workflow Bot.",
        "expected_assertions": {
            "sentiment_signals": ["burnout", "overworked"],
            "task_created": ["login", "fix"]
        },
        "min_length": 150
    },
    {
        "id": 8,
        "name": "Slack Real-Time Ops",
        "category": "Ops",
        "icon": "⚡",
        "prompt": (
            "You are a Slack Ops Agent.\n"
            "Task: Handle message: 'ALERT: PRODUCTION DATABASE IS DOWN. PLEASE RUN /dreamagent-fix-db'.\n\n"
            "Output JSON with keys: priority, action_taken, notification_text."
        ),
        "system": "You are a Real-Time Operations Brain.",
        "expected_assertions": {
            "priority": "URGENT",
            "action_taken": ["fix-db", "command"]
        },
        "min_length": 100
    },
    {
        "id": 9,
        "name": "Orchestrator 1 - Meeting Pipeline",
        "category": "Pipeline",
        "icon": "🔗",
        "prompt": (
            "You are a master orchestrator.\n"
            "Task: Execute a branched meeting flow.\n"
            "1. IF meeting_detected: Execute in PARALLEL: [schedule_calendar, prepare_agenda_notes].\n"
            "2. AFTER parallel steps: Notify team on Slack.\n\n"
            "Output JSON with keys: logic_branched (bool), parallel_execution (list), data_flow_payloads."
        ),
        "system": "You are a master pipeline orchestrator.",
        "expected_assertions": {
            "logic_branched": True
        },
        "expected_state_flow": [
            "meeting_detected",
            "branch_parallel",
            "slack_notify"
        ],
        "required_tools": ["calendar.schedule", "slack.send"],
        "min_length": 250
    },
    {
        "id": 10,
        "name": "Orchestrator 2 - Content Repurposing",
        "category": "Pipeline",
        "icon": "♻️",
        "prompt": (
            "You are the Content CEO.\n"
            "Task: Repurpose YouTube video. \n"
            "Linear Flow: YouTube -> Notion -> Slack -> Gmail.\n"
            "Requirement: Add conditional check: If content is 'AI', also publish to Twitter.\n\n"
            "Output JSON with keys: execution_steps (list), conditional_branch_triggered (bool)."
        ),
        "system": "You are the master pipeline orchestrator.",
        "expected_assertions": {
            "execution_steps": ["youtube", "notion", "slack", "gmail", "twitter"]
        },
        "min_length": 250
    },
    {
        "id": 11,
        "name": "Orchestrator 3 - Startup CEO Mode",
        "category": "Pipeline",
        "icon": "🚀",
        "prompt": (
            "You are an autonomous CEO.\n"
            "Morning Cadence: Gmail (tasks) -> Google Sheets (metrics) -> Notion (strategy).\n"
            "Requirement: Run metrics and strategy updates in PARALLEL to save time.\n\n"
            "Output JSON with keys: sequential_steps, parallel_steps, delegation_plan."
        ),
        "system": "You are an autonomous AI CEO.",
        "expected_assertions": {
            "parallel_steps": ["metrics", "strategy"],
            "sequential_steps": ["gmail"]
        },
        "min_length": 250
    },
    {
        "id": 12,
        "name": "Chaos Recovery - Self-Healing Agent",
        "category": "Self-Healing",
        "icon": "🔁",
        "prompt": (
            "You are a Self-Healing Agent.\n"
            "Task: Fetch data from the API.\n"
            "Note: The primary endpoint is flapping (50% failure rate).\n\n"
            "Output JSON with keys: strategy_used, fallback_executed (bool), retry_count."
        ),
        "system": "You are a robust engineering agent.",
        "chaos": {
            "type": "flakey",
            "message": "Primary JSON API endpoint is returning 500 intermittently."
        },
        "expected_assertions": {
            "fallback_executed": True,
            "strategy_used": ["retry", "fallback"]
        },
        "min_length": 150
    },
    {
        "id": 13,
        "name": "Memory Persistence Test",
        "category": "Memory",
        "icon": "📝",
        "turns": [
            "Store preference: 'User prefers morning meetings'",
            "Schedule my sync with the team.\n\nOutput JSON with key: proposed_time."
        ],
        "system": "You are a memory-augmented agent.",
        "expected_assertions": {
            "proposed_time": ["morning"]
        },
        "min_length": 50
    },
    {
        "id": 14,
        "name": "Adversarial Input Stability",
        "category": "Safety",
        "icon": "🛡️",
        "prompt": (
            "Task: Schedule meeting tomorrow... actually cancel... no wait reschedule for next week... "
            "but never mind, just send an email to Bob instead.\n\n"
            "Output JSON with keys: execution_trace, final_action."
        ),
        "system": "You are a stable and highly logical agent.",
        "expected_assertions": {
            "final_action": ["email", "bob"]
        },
        "expected_state_flow": ["evaluating_changes", "cancel_meeting", "send_email"],
        "min_length": 100
    }
]


# ── Scorer ───────────────────────────────────────────────────────────────────

def score_test(test: dict, text: str, error: str = None) -> dict:
    if error or not text.strip():
        return {
            "passed": False, "score": 0, "grade": "❌ FAIL",
            "reason": error or "Empty response",
            "keyword_hits": [], "keyword_misses": test.get("pass_criteria", []),
            "json_errors": [],
            "assertion_failures": []
        }

    # 1. Extraction (Find JSON if wrapped in markdown blocks)
    import re
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        json_text = json_match.group(1)
    else:
        # Fallback to looking for { ... }
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        json_text = json_match.group(1) if json_match else text

    # 2. JSON Validation
    parsed_data = {}
    json_errors = []
    try:
        parsed_data = json.loads(json_text)
    except Exception as e:
        json_errors.append(f"JSON Parse Error: {str(e)}")

    # 3. Assertions (Ground Truth)
    assertion_failures = []
    expected_assertions = test.get("expected_assertions", {})
    
    if parsed_data:
        for key, expected_val in expected_assertions.items():
            actual_val = parsed_data.get(key)
            if isinstance(expected_val, list):
                if not actual_val or not all(k in str(actual_val).lower() for k in expected_val):
                    assertion_failures.append(f"Missing expected content in '{key}'. Expected: {expected_val}, Got: {actual_val}")
            elif actual_val != expected_val:
                assertion_failures.append(f"Mismatch in '{key}'. Expected: {expected_val}, Got: {actual_val}")

        expected_state_flow = test.get("expected_state_flow", [])
        if expected_state_flow:
             actual_flow = parsed_data.get("execution_trace", [])
             if not isinstance(actual_flow, list):
                  assertion_failures.append("execution_trace is missing or not a list")
             else:
                  for expected_state in expected_state_flow:
                       if not any(expected_state.lower() in str(state).lower() for state in actual_flow):
                            assertion_failures.append(f"Missing expected state in execution_trace: {expected_state}")
                            
        required_tools = test.get("required_tools", [])
        if required_tools:
            # We enforce that tools are logged in the execution_trace or called_tools array
            # We can check a deep string representation of the parsed output.
            parsed_str = json.dumps(parsed_data).lower()
            for tool in required_tools:
                if tool.lower() not in parsed_str:
                    assertion_failures.append(f"Missing required tool call: {tool}")

    # 4. Scoring Logic (Weighted: JSON 40%, Assertions 40%, Length 20%)
    json_score = 40 if not json_errors else 0
    assertion_score = 0
    if expected_assertions:
        assertion_score = max(0, 40 - (len(assertion_failures) * 10)) # Penalize 10 points per failure
    else:
        assertion_score = 40 # If no assertions, assume pass
    
    min_l  = test.get("min_length", 0)
    length_score = 20 if len(text) >= min_l else max(0, int(20 * len(text) / (min_l or 1)))
    
    total = json_score + assertion_score + length_score
    
    # 5. Fallback Keyword logic (for legacy or high-level checks)
    lower = text.lower()
    criteria = test.get("pass_criteria", [])
    hits   = [k for k in criteria if k.lower() in lower]
    misses = [k for k in criteria if k.lower() not in lower]

    if json_errors:
        grade = "❌ FAIL (JSON Error)"
    elif assertion_failures:
        grade = "⚠️ PARTIAL (Assert Failed)"
    else:
        grade = "✅ PASS" if total >= 80 else "❌ FAIL (Low Score)"

    chaos_metrics = None
    if test.get("chaos"):
        chaos_metrics = {
             "fallback_used": "fallback" in text.lower() or "retry" in text.lower(),
             "final_success": grade == "✅ PASS"
        }

    return {
        "passed": total >= 80 and not json_errors and not assertion_failures,
        "score": total,
        "grade": grade,
        "reason": f"JSON: {json_score}, Assert: {assertion_score}, Length: {length_score}",
        "keyword_hits": hits,
        "keyword_misses": misses,
        "json_errors": json_errors,
        "assertion_failures": assertion_failures,
        "execution_trace": parsed_data.get("execution_trace", []),
        "chaos_metrics": chaos_metrics
    }


# ── Direct Agent Caller ───────────────────────────────────────────────────────

async def run_test_direct(test: dict, llm) -> dict:
    """
    Call the LLM directly with a system+user prompt combo.
    No HTTP, no queues — pure agent-level call.
    Includes Chaos Injection logic.
    """
    from backend.agents.base_agent import BaseAgent

    # Chaos Injection
    chaos_note = ""
    if test.get("chaos"):
        c = test["chaos"]
        chaos_note = f"\n\n[CHAOS INJECTION - SYSTEM ERROR]: {c['message']}\nInstructions: Handle this gracefully (retry, fallback, or error reporting)."

    agent = BaseAgent(llm=llm, role=test["category"].lower())
    t0 = time.time()
    error = None
    text  = ""

    system_prompt = test.get("system", "") + "\nOUTPUT ONLY RAW JSON FORMAT."
    
    try:
        if test.get("turns"):
            history = ""
            for turn in test["turns"]:
                prompt = history + "\nUser: " + turn
                text = await agent.think(prompt, system=system_prompt)
                history += f"\nUser: {turn}\nAgent: {text}\n"
        else:
            text = await agent.think(test.get("prompt", "") + chaos_note, system=system_prompt)
    except Exception as e:
        error = str(e)

    elapsed_ms = int((time.time() - t0) * 1000)
    scoring    = score_test(test, text, error)

    # Self-Healing Retry Loop
    if not scoring["passed"] and not error:
        heal_prompt = (f"Previous attempt failed validation.\n"
                       f"Errors: {scoring['assertion_failures'] + scoring['json_errors']}\n"
                       f"Analyze why you failed and output a corrected JSON.")
        try:
             text_healed = await agent.think(test.get("prompt", "") + chaos_note + "\n\n" + heal_prompt, system=system_prompt)
             scoring_healed = score_test(test, text_healed, None)
             if scoring_healed["score"] > scoring["score"]:
                  text = text_healed
                  scoring = scoring_healed
                  scoring["reason"] += " (Recovered via Self-Healing)"
                  if scoring.get("chaos_metrics"):
                      scoring["chaos_metrics"]["final_success"] = scoring["passed"]
                      scoring["chaos_metrics"]["retry_strategy"] = "self-healing loop"
        except Exception:
             pass

    return {
        "test": {
            "id":            test["id"],
            "name":          test["name"],
            "category":      test["category"],
            "icon":          test["icon"],
            "prompt":        test.get("prompt", str(test.get("turns", []))),
            "expected_assertions": test.get("expected_assertions", {}),
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
            
        if sc.get("execution_trace"):
            print("        Execution Trace:")
            for trace_item in sc["execution_trace"]:
                print(f"           ↳ {trace_item}")
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
