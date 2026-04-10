import os
import chromadb
from typing import List, Dict, Any, Optional

# Shared singleton chroma path
CHROMA_DATA_DIR = os.getenv("CHROMA_DATA_DIR", "DreamAgent/vector_data")
# Ensure directory exists
os.makedirs(CHROMA_DATA_DIR, exist_ok=True)

class VectorDBClient:
    def __init__(self):
        # Initialize Persistent Client
        self.client = chromadb.PersistentClient(path=CHROMA_DATA_DIR)
        
        # Dynamic Collections used to prevent dimension collision
        # Collections are retrieved via specific bot ID at query time

    def get_collection(self, bot_id: str, provider: str = "local"):
        """Retrieves or creates a bot-specific isolated dimension space container. Handles mismatch safely."""
        safe_id = str(bot_id).replace("-", "_")
        name = f"bot_{safe_id}"
        
        dims = {"openai": 1536, "gemini": 768, "local": 384}
        dim = dims.get(provider.lower(), 384)
        
        def _get_or_create(col_name):
            try:
                col = self.client.get_collection(name=col_name)
                if col.metadata and col.metadata.get("dim") and col.metadata.get("dim") != dim:
                    # Mismatch -> return None
                    return None
                return col
            except ValueError:
                return self.client.create_collection(
                    name=col_name,
                    metadata={
                        "hnsw:space": "cosine",
                        "embedding_provider": provider,
                        "dim": dim
                    }
                )

        # Try default name
        col = _get_or_create(name)
        if col:
            return col
            
        # If None, it means dimension mismatch exists.
        # Fallback to _v2, _v3, etc. safely.
        print(f"[RAG] Dimension mismatch detected for {name}. Resolving safely...")
        for i in range(2, 10):
            safe_name = f"{name}_v{i}"
            col = _get_or_create(safe_name)
            if col:
                return col
        
        # Absolute fallback
        return self.client.create_collection(
            name=f"{name}_fallback_{dim}",
            metadata={"hnsw:space": "cosine", "embedding_provider": provider, "dim": dim}
        )

    def get_task_collection(self, bot_id: str, provider: str = "local"):
        """Isolated Task Memory container strictly for the Autonomous Engine loop strategies."""
        safe_id = str(bot_id).replace("-", "_")
        name = f"tasks_{safe_id}"
        
        dims = {"openai": 1536, "gemini": 768, "local": 384}
        dim = dims.get(provider.lower(), 384)
        
        try:
            col = self.client.get_collection(name=name)
            if col.metadata and col.metadata.get("dim") and col.metadata.get("dim") != dim:
                raise Exception(f"Task Embedding mismatch. Collection is {col.metadata.get('dim')}d, model is {dim}d.")
            return col
        except ValueError:
            pass
            
        return self.client.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine", "embedding_provider": provider, "dim": dim}
        )

    def wipe_bot_vectors(self, bot_id: str):
        """
        Wipes the entire vector space for a bot. 
        MANDATORY constraint when a user switches their Provider model 
        (e.g., Local [384d] to OpenAI [1536d]) to prevent dimension crashes.
        """
        safe_id = str(bot_id).replace("-", "_")
        name = f"bot_{safe_id}"
        print(f"[RAG] 🧹 WIPING VECTORS FOR: {name} (Model Change Event)")
        try:
            self.client.delete_collection(name)
        except Exception as e:
            print(f"[RAG] Wipe failed or collection didn't exist: {e}")

    def store_chunks(self, chunks: List[str], embeddings: List[List[float]], doc_id: str, bot_id: str, user_id: str, provider: str = "local"):
        """
        Stores chunked text into ChromaDB strictly per-bot.
        Uses exact metadata injection for strong filtering isolate.
        """
        if not chunks or not embeddings or len(chunks) != len(embeddings):
            return

        import hashlib
        chunk_ids = []
        for chunk in chunks:
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
            chunk_ids.append(f"{doc_id}_{chunk_hash}")
        metadatas = [
            {
                "doc_id": doc_id,
                "bot_id": str(bot_id),
                "user_id": str(user_id)
            }
            for _ in chunks
        ]

        collection = self.get_collection(bot_id, provider)
        collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=chunk_ids
        )
        print(f"[RAG] Stored {len(chunks)} chunks for doc {doc_id} (bot: {bot_id})")

    def search(self, embedding: List[float], bot_id: str, user_id: str, provider: str = "local", file_ids: Optional[List[str]] = None, top_k: int = 5) -> List[str]:
        """
        Retrieves the most relevant document chunks based on semantic similarity.
        ALWAYS filters by bot_id + user_id. Supports optional file_ids filtering.
        """
        where_clause = {
            "$and": [
                {"bot_id": str(bot_id)},
                {"user_id": str(user_id)}
            ]
        }
        
        if file_ids and len(file_ids) > 0:
            where_clause["$and"].append({
                "doc_id": {"$in": file_ids}
            })

        # Query the specific collection
        collection = self.get_collection(bot_id, provider)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where_clause
        )

        retrieved_chunks = []
        if results and "documents" in results and results["documents"] and results["documents"][0]:
            docs = results["documents"][0]
            dists = results["distances"][0] if "distances" in results and results["distances"] else [0] * len(docs)
            
            valid_chunks = []
            valid_dists = []
            for doc, dist in zip(docs, dists):
                # Cosine distance: lower is closer (0.0 is perfect match)
                if dist < 0.8:
                    valid_chunks.append(doc)
                    valid_dists.append(dist)
            
            if valid_chunks:
                max_len = max(len(chunk) for chunk in valid_chunks)
                if max_len == 0: max_len = 1
                
                seen = set()
                scored_chunks = []
                
                for chunk, dist in zip(valid_chunks, valid_dists):
                    # Dedup explicit check
                    if chunk[:100] not in seen:
                        seen.add(chunk[:100])
                        # Score: distance = relevance (0 is perfect, so 1-dist is higher=better)
                        score = (1 - dist) * 0.7 + (len(chunk) / max_len) * 0.3
                        scored_chunks.append((chunk, score))
                
                # Ranked highest score first
                retrieved_chunks = [c[0] for c in sorted(scored_chunks, key=lambda x: x[1], reverse=True)]

        print(f"[RAG] Retrieved {len(retrieved_chunks)} valid chunks for user {user_id}")
        return retrieved_chunks

# Global Singleton instance
vector_db = VectorDBClient()
