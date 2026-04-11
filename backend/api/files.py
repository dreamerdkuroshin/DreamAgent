"""
backend/api/files.py  (v2 — Hardened)

Upload endpoint with:
  - Redis/Dragonfly primary storage (TTL = 1 hour)
  - In-process dict fallback when Redis is unavailable
  - Structured preview payload so UI stays fast
  - No dependency on Bot DB row or embedding pipeline
"""
import json
import logging
import faiss
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session

# Optional local embeddings for FAISS RAG Layer
try:
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    embedder = None

from backend.core.database import get_session
from backend.services.file_processor import file_processor, CHUNK_SIZE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/files", tags=["files"])

FILE_TTL_SECONDS = 3600  # 1 hour

# --- Vector Retrieval Layer (RAG) ---
global_faiss_index = None
global_chunk_metadata = []

def split_text(text: str, chunk_size: int) -> list:
    """Smart chunking for massive file uploads to prevent context explosion."""
    if not text: return []
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

def process_and_store_chunks(file_id: str, chunks: list):
    """File Upload -> Chunk -> Embed -> Store (FAISS)"""
    global global_faiss_index, global_chunk_metadata
    if not embedder or not chunks:
        return
        
    logger.info(f"Embedding {len(chunks)} chunks for {file_id}...")
    try:
        embeddings = embedder.encode(chunks)
        dim = embeddings.shape[1]
        
        if global_faiss_index is None:
            global_faiss_index = faiss.IndexFlatL2(dim)
            
        global_faiss_index.add(np.array(embeddings).astype('float32'))
        
        for c in chunks:
            global_chunk_metadata.append({"file_id": file_id, "text": c})
    except Exception as e:
        logger.error(f"Vector Store error: {e}")

def retrieve_top_chunks(query: str, top_k: int = 5) -> list:
    """User Query -> Retrieve Top Chunks -> Send to LLM"""
    global global_faiss_index, global_chunk_metadata
    if not embedder or global_faiss_index is None or global_faiss_index.ntotal == 0:
        return []
        
    q_vec = embedder.encode([query])
    distances, indices = global_faiss_index.search(np.array(q_vec).astype('float32'), top_k)
    
    results = []
    for idx in indices[0]:
        if idx >= 0 and idx < len(global_chunk_metadata):
            results.append(global_chunk_metadata[idx]["text"])
    return results

def _store_file(file_id: str, payload: dict) -> str:
    """Persist to unified cache layer (Dragonfly → local fallback)."""
    from backend.core.cache import cache_set
    cache_set(f"upload:{file_id}", payload, ttl=FILE_TTL_SECONDS)
    from backend.core.dragonfly_manager import dragonfly
    return "dragonfly" if dragonfly.is_connected() else "local"

def _fetch_file(file_id: str) -> dict | None:
    from backend.core.cache import cache_get
    return cache_get(f"upload:{file_id}")

def get_uploaded_file(file_id: str) -> dict | None:
    return _fetch_file(file_id)


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    bot_id: str = Form("local_gui"),
    user_id: str = Form("web_client"),
    db: Session = Depends(get_session),
):
    """
    Accepts any supported file, extracts safe text, chunks it, and updates Vector DB.
    """
    try:
        content = await file.read()

        # 1. Extract + sanitize
        result = file_processor.extract_content(content, file.filename)

        if result.error and not result.content_text:
            raise HTTPException(status_code=400, detail=result.error)

        # 2. Smart Chunking + RAG Injection
        chunks = split_text(result.content_text, CHUNK_SIZE)
        process_and_store_chunks(result.file_id, chunks)

        # 3. Special file handler: Google JSON, API key files, etc.
        special_analysis = None
        try:
            from backend.api.key_injector import analyze_uploaded_file
            special_analysis = analyze_uploaded_file(
                filename=file.filename,
                content_text=result.content_text,
                file_type=result.file_type,
            )
        except Exception as _sa_err:
            logger.warning(f"[Files] Special analysis failed: {_sa_err}")

        # 4. Persist core metadata to DB/Cache
        payload = {
            "file_id":     result.file_id,
            "filename":    result.filename,
            "file_type":   result.file_type,
            "category":    result.category,
            "content":     result.content_text,   # For exact fallback access
            "raw_preview": result.raw_preview,
            "metadata":    result.metadata,
        }
        storage_backend = _store_file(result.file_id, payload)

        logger.info(
            f"[Files] Stored {file.filename} -> {result.file_id} "
            f"via {storage_backend} (category={result.category}, chunks={len(chunks)})"
        )

        response_data = {
            "status":         "success",
            "doc_id":         result.file_id,
            "filename":       file.filename,
            "category":       result.category,
            "preview":        result.raw_preview[:500],
            "full_available": True,
            "storage":        storage_backend,
        }

        # Attach special analysis results (Google JSON, key detection, etc.)
        if special_analysis:
            response_data["special_analysis"] = {
                "type":           special_analysis.get("json_type", "key_scan"),
                "gmail_enabled":  special_analysis.get("gmail_enabled", False),
                "services":       special_analysis.get("enabled_services", []),
                "actions":        special_analysis.get("actions", []),
                "reply":          special_analysis.get("reply", ""),
            }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Files] Upload error for {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{file_id}/content")
async def get_file_content(file_id: str):
    payload = _fetch_file(file_id)
    if not payload:
        raise HTTPException(
            status_code=404,
            detail="File not found or expired.",
        )
    return {
        "file_id":  payload["file_id"],
        "filename": payload["filename"],
        "category": payload["category"],
        "content":  payload["content"],
    }
