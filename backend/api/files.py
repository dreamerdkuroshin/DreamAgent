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
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_session
from backend.services.file_processor import file_processor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/files", tags=["files"])

# TTL for uploaded file payloads
FILE_TTL_SECONDS = 3600  # 1 hour


def _store_file(file_id: str, payload: dict) -> str:
    """Persist to unified cache layer (Dragonfly → local fallback, auto-migrates)."""
    from backend.core.cache import cache_set
    cache_set(f"upload:{file_id}", payload, ttl=FILE_TTL_SECONDS)
    from backend.core.dragonfly_manager import dragonfly
    return "dragonfly" if dragonfly.is_connected() else "local"


def _fetch_file(file_id: str) -> dict | None:
    """Retrieve from unified cache layer."""
    from backend.core.cache import cache_get
    return cache_get(f"upload:{file_id}")


# Public helper — used by chat.py and orchestrator_agent.py
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
    Accepts any supported file, extracts safe text, and returns a handle.
    Does NOT require Bot DB row or embedding pipeline.
    """
    try:
        content = await file.read()

        # 1. Extract + sanitize + truncate
        result = file_processor.extract_content(content, file.filename)

        if result.error and not result.content_text:
            raise HTTPException(status_code=400, detail=result.error)

        # 2. Persist to unified cache layer
        payload = {
            "file_id":     result.file_id,
            "filename":    result.filename,
            "file_type":   result.file_type,
            "category":    result.category,
            "content":     result.content_text,   # sanitized + truncated
            "raw_preview": result.raw_preview,
            "metadata":    result.metadata,
        }
        storage_backend = _store_file(result.file_id, payload)

        logger.info(
            f"[Files] Stored {file.filename} → {result.file_id} "
            f"via {storage_backend} (category={result.category})"
        )

        # 3. Return fast preview — UI stays snappy
        return {
            "status":         "success",
            "doc_id":         result.file_id,
            "filename":       file.filename,
            "category":       result.category,
            "preview":        result.raw_preview[:500],
            "full_available": True,
            "storage":        storage_backend,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Files] Upload error for {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}/content")
async def get_file_content(file_id: str):
    """Return full extracted content for a previously uploaded file."""
    payload = _fetch_file(file_id)
    if not payload:
        raise HTTPException(
            status_code=404,
            detail="File not found or expired (TTL: 1 hour). Please re-upload.",
        )
    return {
        "file_id":  payload["file_id"],
        "filename": payload["filename"],
        "category": payload["category"],
        "content":  payload["content"],
    }
