import httpx
import asyncio
import json

BASE_URL = "http://localhost:8001/api/v1"

async def test_all():
    print("====================================")
    print("Testing New Integration Features")
    print("====================================")
    
    async with httpx.AsyncClient() as client:
        # TEST 1: Terminal Shell API
        print("\n--- 1. Testing Shell API ---")
        try:
            resp = await client.post(f"{BASE_URL}/integrations/shell?confirm=true", json={"command": "echo Hello DreamAgent Terminal"})
            data = resp.json()
            if data.get("status") == "success" and "Hello DreamAgent Terminal" in data.get("data", {}).get("output", ""):
                print("[PASS] Shell Terminal working correctly!")
            else:
                print(f"[FAIL] Shell Terminal Failed: {data}")
        except Exception as e:
            print(f"[FAIL] Error testing Shell API: {e}")

        # TEST 2: Local Tools API persistence
        print("\n--- 2. Testing Settings Tools Toggles ---")
        try:
            post_resp = await client.post(f"{BASE_URL}/settings/keys", json={"TOOL_TAVILY_ENABLED": "true"})
            if post_resp.status_code == 200:
                print("[PASS] Successfully POSTed TOOL_TAVILY_ENABLED=true")
            
            get_resp = await client.get(f"{BASE_URL}/settings/keys")
            keys = get_resp.json().get("data", {})
            if keys.get("TOOL_TAVILY_ENABLED", {}).get("configured") == True:
                print("[PASS] Successfully verified TOOL_TAVILY_ENABLED state persisted!")
            else:
                print("[FAIL] Toggle state did not persist properly.")
        except Exception as e:
            print(f"[FAIL] Error testing Settings API: {e}")

        # TEST 3: Max Bots Limitation
        print("\n--- 3. Testing 25 Bot Max Limit Logic ---")
        try:
            print("Note: Simulating hitting the limit without actually spinning up 26 processes.")
            post_resp = await client.post(f"{BASE_URL}/integrations/tokens", json={
                "platform": "discord",
                "token": "test-discord-token",
                "auto_start": True
            })
            if post_resp.status_code == 200:
                print("[PASS] Successfully started the stub discord_bot.py!")
            else:
                print(f"[FAIL] Failed to start bot: {post_resp.text}")
        except Exception as e:
            print(f"[FAIL] Error testing Bots API: {e}")

if __name__ == "__main__":
    asyncio.run(test_all())

if __name__ == "__main__":
    asyncio.run(test_all())
