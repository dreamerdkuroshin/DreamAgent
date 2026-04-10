import asyncio
import sys
import io
# Force utf-8 output on Windows to avoid cp1252 emoji errors
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from backend.orchestrator.priority_router import detect_intent
from backend.agents.specialized.file_agent import _parse_file_query

PASS = "[PASS]"
FAIL = "[FAIL]"

def check(label, got, expected):
    ok = got == expected
    marker = PASS if ok else FAIL
    print(f"  {marker} {label}")
    print(f"         Got: {got}  |  Expected: {expected}")
    return ok

def test_intent_routing():
    print("--- Testing Intent Routing ---")
    results = []

    results.append(check(
        "bitcoin today -> finance",
        detect_intent("what is price of bitcoin today"),
        "finance"
    ))
    results.append(check(
        "crypto price -> finance",
        detect_intent("show me crypto market prices"),
        "finance"
    ))
    results.append(check(
        "latest news -> news",
        detect_intent("latest news from japan"),
        "news"
    ))
    results.append(check(
        "build a website -> builder",
        detect_intent("create website for my pizza shop"),
        "builder"
    ))
    results.append(check(
        "hello -> chat",
        detect_intent("hello how are you"),
        "chat"
    ))

    passed = sum(results)
    print(f"\nIntent Routing: {passed}/{len(results)} passed\n")

def test_file_regex():
    print("--- Testing File Agent Regex ---")
    results = []

    got1, _ = _parse_file_query("show index.html content")
    results.append(check("show index.html", got1, "index.html"))

    got2, _ = _parse_file_query("read /usr/src/app/main.py and explain")
    results.append(check("path with slashes", got2, "/usr/src/app/main.py"))

    got3, _ = _parse_file_query("analyze main.py, it seems broken")
    results.append(check("analyze main.py with comma", got3, "main.py"))

    passed = sum(results)
    print(f"\nFile Regex: {passed}/{len(results)} passed\n")

async def test_ddgs():
    print("--- Testing DDGS Import & Live Fetch ---")
    try:
        import time, random
        from ddgs import DDGS
        print("  [PASS] ddgs module imported successfully")
        print("  Sleeping 2s to respect rate limits...")
        time.sleep(2)
        with DDGS() as ddgs:
            results = list(ddgs.news("AI technology", max_results=2))
        if results:
            print(f"  [PASS] Live news fetch: {len(results)} result(s) returned")
            print(f"         Sample: {results[0].get('title', 'N/A')[:60]}")
        else:
            print("  [WARN] DDGS returned 0 results (may be rate limited)")
    except Exception as e:
        print(f"  [FAIL] DDGS error: {e}")
    print("")

async def main():
    test_intent_routing()
    test_file_regex()
    await test_ddgs()
    print("=" * 50)
    print("Architecture test run complete.")

if __name__ == "__main__":
    asyncio.run(main())
