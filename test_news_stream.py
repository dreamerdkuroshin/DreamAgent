import httpx
import asyncio
import json

async def test_stream():
    url = "http://127.0.0.1:8000/api/v1/chat/stream"
    
    print("--- 1. Testing Normal News Query ---")
    query = "latest news in france"
    params = {"query": query, "taskId": "test-task-1"}
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            async with client.stream("GET", url, params=params) as response:
                print(f"Status: {response.status_code}")
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        print(f"Stream: {chunk.strip()}")
        except Exception as e:
            print(f"Failed to connect: {e}")
            
    print("\n--- 2. Testing Retry Mechanism ---")
    
    # We will pretend the previous task failed or we want to retry
    # Note: to test retry, the task must exist in _USER_FAILED_TASKS, but since
    # it's just a test and we might not have a failed task, let's inject one manually
    # or just see what happens if we retry an empty one.
    
    params_retry = {"query": '{"action": "retry_task"}', "taskId": "test-task-2", "convoId": "local_user"}
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            async with client.stream("GET", url, params=params_retry) as response:
                print(f"Status: {response.status_code}")
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        print(f"Stream: {chunk.strip()}")
        except Exception as e:
            print(f"Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(test_stream())
