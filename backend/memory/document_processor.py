import uuid
import asyncio
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import fitz  # PyMuPDF

from backend.memory.vector_db import vector_db

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        try:
            print("[RAG] Loading fast sentence-transformers model...")
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[RAG] Failed to load SentenceTransformer: {e}")
            _embedder = None
    return _embedder

def get_query_embedding(text: str) -> List[float]:
    embedder = get_embedder()
    if not embedder:
        return []
    return embedder.encode([text])[0].tolist()

def extract_text(file_content: bytes, filename: str) -> str:
    """Extracts text from widely used document formats (PDF, TXT)"""
    text = ""
    # Check if PDF
    if filename.lower().endswith(".pdf"):
        doc = fitz.open(stream=file_content, filetype="pdf")
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    else:
        # Fallback raw text decoding
        text = file_content.decode("utf-8", errors="ignore")
        
    return text.strip()

def chunk_text(text: str, size: int = 500, overlap: int = 100) -> List[str]:
    """
    Semantic sentence-aware chunking algorithm.
    Size constraint focuses on character length approximation of chunks.
    This respects sentence boundaries to prevent destroying semantic integrity.
    """
    sentences = text.split(". ")
    chunks = []
    current = ""
    
    for sentence in sentences:
        if len(current) + len(sentence) < size:
            current += sentence + ". "
        else:
            chunks.append(current.strip())
            # Simple overlap simulation: start next chunk with the most recent sentence if it's not huge
            current = sentence + ". "

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c.strip()]

async def process_and_store_document(file_content: bytes, filename: str, bot_id: str, user_id: str, provider: str = "local") -> str:
    """
    Main ingestion pipeline: Parse → Chunk → Batch Embed → Vector DB
    (Fully async to support high-latency API embedding providers like OpenAI if selected)
    """
    from backend.llm.embedding_provider import get_embedding
    
    doc_id = str(uuid.uuid4())
    
    # 1. Parse content
    text = extract_text(file_content, filename)
    if not text:
        return None

    # 2. Slice text cleanly by sentences
    chunks = chunk_text(text, size=800) # 800 chars roughly maps to ~200 tokens
    
    if not chunks:
        return None
        
    # 3. Embed chunks (Iterative async)
    # Even though OpenAI doesn't natively batch well over text arrays in simple wrappers, 
    # we can do concurrent tasks if we want. For simplicity, we'll embed sequentially or via gather.
    embeddings_list = []
    
    print(f"[RAG Ingest] Generating {len(chunks)} embeddings using {provider.upper()}")
    
    # We embed chunks individually via the provider.
    # Note: SentenceTransformers batches automatically. OpenAI handles lists nicely in their raw API
    # but our wrapper handles simple `str`. To make it generic:
    for chunk in chunks:
        vec = await get_embedding(chunk, provider=provider)
        if not vec:
             return None # Fail gracefully if network cuts out
        embeddings_list.append(vec)

    # 4. Push to Vector DB
    vector_db.store_chunks(
        chunks=chunks,
        embeddings=embeddings_list,
        doc_id=doc_id,
        bot_id=bot_id,
        user_id=user_id
    )
    
    return doc_id
