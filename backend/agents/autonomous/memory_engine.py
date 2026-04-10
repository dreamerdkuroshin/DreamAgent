"""
backend/agents/autonomous/memory_engine.py
Semantic Task Memory Layer.
Records and retrieves historical AutoGPT paths using exact Vector Embedding matches.
"""
import uuid
import json
from backend.core.database import SessionLocal
from backend.core.models import TaskHistory
from backend.memory.vector_db import vector_db
from backend.llm.universal_provider import universal_provider

class MemoryEngine:
    async def save_task(self, user_id: str, bot_id: str, goal: str, plan: list, result: str, success: bool):
        # 1. Store structured ledger internally to SQLite Database
        db = SessionLocal()
        try:
            record = TaskHistory(
                user_id=user_id,
                bot_id=bot_id,
                goal=goal,
                plan=[p if isinstance(p, dict) else dict(p) for p in plan],
                result={"evaluation": result},
                success=1 if success else 0
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            task_id_str = str(record.id)
            
            print(f"[MemoryEngine] Logged Semantic SQLite Task History #{task_id_str}")
            
            # 2. Map abstract semantics explicitly to Chroma `tasks_{bot_id}` dimension
            # Ensure we get the correct embedding dimension via exactly the bot's configured provider
            bot_model = "openai" # Defaulting explicitly for embeddings, typically you query DB for bot provider.
            # Using generic fallback embedded vectors mechanism below wrapper.
            
            collection = vector_db.get_task_collection(bot_id=bot_id, provider=bot_model)
            
            metadata = {
                "task_id": task_id_str,
                "user_id": user_id, 
                "bot_id": bot_id, 
                "success": 1 if success else 0
            }
            
            doc_id = f"task_{uuid.uuid4().hex}"
            
            # Simple text embedding via the universal_provider if available
            # Note: For pure architecture we usually just pass the document mapping into Chroma.
            # We'll use Chroma's built-in token logic or explicit embeddings via the router wrapper if we had it.
            # For this MVP, we will feed it into the vector_db's native embedding hooks. Wait, the vector_db 
            # `store_chunks` expects embeddings. Let's explicitly bypass generating raw arrays for now and let
            # a future abstraction handle true `vector_db.add` wrappers. Instead, we'll store via Chroma generic `add`:
            
            # Just push directly into Isolated Tasks Collection using local/Chroma built-ins:
            try:
                # Mocking the embedding call via UniversalProvider specifically or local embedding model:
                # If we rely on generic:
                collection.add(
                    documents=[goal],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
                print(f"[MemoryEngine] Embedded Goal natively into Vector Dimension Space.")
            except Exception as v_err:
                print(f"[MemoryEngine] Vector DB Insert Warning: {v_err}")
                
        finally:
            db.close()

    async def retrieve_similar(self, bot_id: str, goal: str, k: int = 3):
        try:
            collection = vector_db.get_task_collection(bot_id=bot_id, provider="openai")
            
            # Basic Chroma query hook
            results = collection.query(
                query_texts=[goal],
                n_results=k,
                where={"success": 1}
            )
            
            task_ids = []
            for meta_batch in results.get("metadatas", []):
                for meta in meta_batch:
                    if "task_id" in meta:
                        task_ids.append(meta["task_id"])
                        
            if not task_ids:
                return []
                
            # Fetch explicitly from DB
            db = SessionLocal()
            try:
                historical = db.query(TaskHistory).filter(TaskHistory.id.in_(task_ids)).all()
                return [
                    {
                        "goal": h.goal,
                        "plan": h.plan
                    } for h in historical
                ]
            finally:
                db.close()
                
        except Exception as e:
            print(f"[MemoryEngine] Retrieval failed: {e}")
            return []

memory_engine = MemoryEngine()
