import asyncio
import httpx
import json
import time

API_URL = "http://127.0.0.1:8001/api/v1/chat/stream"

TASKS = [
    {
        "id": 1,
        "name": "Startup Launch Simulation",
        "prompt": "Launch a Gen Z clothing brand in 7 days"
    },
    {
        "id": 2,
        "name": "SaaS from Idea",
        "prompt": "Build an AI tool like Notion but for gamers. Must be open-source and deployable"
    },
    {
        "id": 3,
        "name": "Debate Engine Test",
        "prompt": "Should I build in public or stay private?"
    },
    {
        "id": 4,
        "name": "Deep Research Task",
        "prompt": "Find 5 viral GitHub projects in the last 30 days and explain why they blew up"
    },
    {
        "id": 5,
        "name": "Autonomous Coding Loop",
        "prompt": "Build a REST API with FastAPI + auth + tests"
    },
    {
        "id": 6,
        "name": "Self-Improvement Loop",
        "prompt": "Analyze your own system and improve performance"
    },
    {
        "id": 7,
        "name": "Failure Injection Test",
        "prompt": "Complete task even if one agent fails randomly. I will simulate killing research."
    },
    {
        "id": 8,
        "name": "Real Monetization Task",
        "prompt": "Make ₹10,000 online in 7 days with zero budget"
    },
    {
        "id": 9,
        "name": "Multi-Step Execution Chain",
        "prompt": "Create a YouTube channel, generate 10 video ideas, scripts, thumbnails, and posting schedule"
    },
    {
        "id": 10,
        "name": "Chaos Test",
        "prompt": "Build, launch, and market an AI product — and adapt strategy based on failures"
    }
]

async def run_task(task, client):
    import urllib.parse
    print(f"\n[{task['id']}/10] Starting: {task['name']}")
    print(f"Prompt: {task['prompt']}")
    
    start = time.time()
    final_result = ""
    
    try:
        url = f"{API_URL}?query={urllib.parse.quote(task['prompt'])}&taskId=test_{task['id']}&provider=auto"
        async with client.stream("GET", url, timeout=300.0) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        payload = json.loads(line[6:])
                        if payload.get("type") == "final":
                            final_result = payload.get("content", "")
                        elif payload.get("type") == "step":
                            print(f"  -> {payload.get('content')}")
                        elif payload.get("type") == "error":
                            print(f"  [ERROR] -> {payload.get('content')}")
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        final_result = f"Failed to execute: {str(e)}"

    duration = time.time() - start
    print(f"-> Completed in {duration:.1f}s")
    
    return {
        "id": task["id"],
        "name": task["name"],
        "duration": duration,
        "output": final_result
    }

async def main():
    results = []
    print("🚀 Initializing DreamAgent 10-Task Stress Test Matrix...")
    
    async with httpx.AsyncClient() as client:
        # Run sequentially to avoid rate limiting public free APIs or overheating local Ollama
        for task in TASKS:
            res = await run_task(task, client)
            results.append(res)
            
            with open("stress_test_report.md", "a", encoding="utf-8") as f:
                f.write(f"\\n## Test {res['id']}: {res['name']}\\n")
                f.write(f"**Execution Time:** {res['duration']:.1f}s\\n\\n")
                f.write(res['output'] + "\\n\\n---\\n")
                
    print("\\n✅ All tests completed! Results saved to stress_test_report.md")

if __name__ == "__main__":
    open("stress_test_report.md", "w", encoding="utf-8").write("# DreamAgent 10-Task Stress Test Results\\n\\n")
    asyncio.run(main())
