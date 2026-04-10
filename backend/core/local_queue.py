"""
backend/core/local_queue.py

High Performance Async Queues for Local/Dev Mode Execution.
Prevents busy-loops by utilizing native asyncio blocking. 
Features explicit Priority routing and a Dead Letter tracking cache.
"""
import asyncio
from typing import Dict, List, Any

class LocalQueues:
    def __init__(self):
        self.complex = asyncio.Queue()
        self.medium  = asyncio.Queue()
        self.simple  = asyncio.Queue()
        
        # Dead Letter Queue for tracking unrecoverable failures locally
        self.dead_letter: List[Dict[str, Any]] = []

    def get_queue(self, q_name: str) -> asyncio.Queue:
        if q_name == "tasks:complex": return self.complex
        if q_name == "tasks:medium":  return self.medium
        if q_name == "tasks:simple":  return self.simple
        return self.medium
        
    def enqueue(self, q_name: str, payload: dict):
        q = self.get_queue(q_name)
        q.put_nowait(payload)

local_queues = LocalQueues()
