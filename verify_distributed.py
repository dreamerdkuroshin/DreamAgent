import asyncio
import uuid
import json
import os
import sys

from backend.core.task_router import dispatch_task
from backend.core.dragonfly_manager import dragonfly

async def main():
    print("Testing Distributed Task Dispatch for MULTI-AGENT BUILDER...")
    os.environ["EXECUTION_MODE"] = "distributed"
    
    await dragonfly.connect()
    
    task_id = str(uuid.uuid4())
    # "build" and > 10 words, and "code", will classify as complex
    payload = {
        "task_id": task_id,
        "query": "build a custom discord bot in python code with logging and advanced features",
        "file_ids": "",
        "convo_id": "test_convo",
        "provider": "auto",
        "model": ""
    }
    
    print(f"Dispatching task {task_id} into Load Balancer...")
    # This directly simulates what chat.py does when speed="complex" for a builder
    queued_id = await dispatch_task(payload)
    print(f"Assigned ID: {queued_id}")

    client = dragonfly.get_client()
    queue_len = client.llen("tasks:complex")
    print(f"Items in tasks:complex queue: {queue_len}")

if __name__ == "__main__":
    asyncio.run(main())
