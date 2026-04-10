import pytest

def test_core_imports():
    from core.agent import DreamAgent
    from core.autonomous import AutonomousAgent
    
    # Assert they can be instantiated
    assert DreamAgent is not None
    assert AutonomousAgent is not None

def test_sandbox_imports():
    from sandbox.sandbox import Sandbox
    s = Sandbox()
    assert s is not None

def test_memory_imports():
    from memory.manager import MemoryManager
    from memory.vector_store import VectorStore
    assert MemoryManager is not None
    assert VectorStore is not None

def test_db_imports():
    from db.db import get_conn, get_api_key
    assert get_conn is not None

def test_queue_imports():
    from queue.worker import celery_app
    from queue.tasks import run_agent_task
    assert celery_app is not None
    assert run_agent_task is not None
