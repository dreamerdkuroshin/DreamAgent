"""
backend/agents/autonomous/memory.py
Autonomous Task memory store.
Currently relies on in-memory dict, tracks step outputs and goal state.
"""

class TaskMemory:
    def __init__(self):
        self.store = {}

    def save(self, task_id: str, data: dict):
        self.store[task_id] = data

    def get(self, task_id: str):
        return self.store.get(task_id)

task_memory = TaskMemory()
