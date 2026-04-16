"""
backend/api/chat.py (v1.0)

Changes:
- Engine instantiated outside generator (fixes 'engine not found' lint)
- v1.0 structured SSE: rich trace events with role / attempt / timestamp
- Support for task cancellation and reconnection
"""

import logging
import time
import asyncio
import json
import uuid
import re
from concurrent.futures import ThreadPoolExecutor

# Key injection — detect API keys in chat messages and persist them
try:
    from backend.api.key_injector import detect_and_store_keys, analyze_uploaded_file as _analyze_file
    _KEY_INJECTION_AVAILABLE = True
except Exception as _ki_err:
    _KEY_INJECTION_AVAILABLE = False
    logger_placeholder = logging.getLogger(__name__)
    logger_placeholder.warning(f"[Chat] Key injector not loaded: {_ki_err}")

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

from backend.core.database import get_session, SessionLocal
from backend.react import ReActEngine
from backend.core.task_queue import enqueue_task, redis_conn
from backend.api.chat_worker import background_agent_loop
from backend.memory.memory_manager import build_context, categorize
from backend.memory.memory_service import store_memory
from backend.safety import is_safe, check_rate
from backend.services import conversation_service

# Speed-based routing core
from backend.core.persona_engine import classify_speed, get_persona_prompt
from backend.core.fast_replies import get_instant_reply
from backend.core.semantic_cache import find_similar, store, rewrite_or_return
from backend.llm.universal_provider import UniversalProvider


# Fix #13: Connect PromptInjectionGuard (DAN/jailbreak/base64 detection)
try:
    import sys as _sys, os as _os
    _safety_path = _os.path.join(_os.path.dirname(__file__), '..', '..', 'safety')
    if _safety_path not in _sys.path:
        _sys.path.insert(0, _safety_path)
    from prompt_injection_guard import PromptInjectionGuard as _PIGuard
    _pi_guard = _PIGuard()
    _USE_PI_GUARD = True
except Exception:
    _pi_guard = None
    _USE_PI_GUARD = False

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    conversation_id: int
    message: str
    provider: str = "auto"
    model: str = ""

async def save_message_to_db(convo_id: int, role: str, content: str, provider: str = "", model: str = "") -> int | None:
    """DB write that returns the saved message ID (or None on failure)."""
    try:
        with SessionLocal() as db:
            msg = conversation_service.create_message(db, convo_id, role, content, provider=provider, model=model)
            return msg.id if msg else None
    except Exception as e:
        logger.error(f"[DB] Failed to save {role} message: {e}")
        return None

def needs_complex_routing(prompt: str, context: dict) -> bool:
    """Forces the LLM through the Orchestrator instead of Fast Paths."""
    p_lower = prompt.lower()
    words = p_lower.split()

    # 1. Realtime Tools Guard (priority even if query is short)
    if any(k in p_lower for k in ["price", "today", "current", "latest", "news", "live", "search"]):
        return True

    # 2. Builder Mode Guard (highest priority to launch UI widgets, even for short queries like "making website")
    from backend.builder.router import is_builder_request
    if context.get("builder_preferences"):
        return True
    if is_builder_request(p_lower):
        return True

    # 3. Platform Bot & Setup Guards
    import re
    BOT_CMD_RE = re.compile(
        r'(telegram|discord|slack|whatsapp).*?'
        r'([A-Za-z0-9_\-\.:]{30,250})',
        re.IGNORECASE | re.DOTALL
    )
    STOP_BOT_RE = re.compile(
        r'(?:stop|kill|terminate|turn\s*off|disable)\s*(telegram|discord|slack|whatsapp)\s*(?:bot)?',
        re.IGNORECASE
    )
    API_KEY_RE = re.compile(
        r'(?:my\s+)?(?:gemini|openai|tavily|anthropic|stripe|supabase|ahrefs|groq|huggingface|resend)'
        r'[^:]*(?:key|token|api)\s*(?:is)?\s*:?\s*([A-Za-z0-9\-\_:.]{10,})',
        re.IGNORECASE
    )
    KEY_VALUE_RE = re.compile(
        r'\b(?:sk_(?:live|test)_|pk_(?:live|test)_|sk-ant-|tvly-|sb_publishable_|AIza|gsk_|hf_|re_)[A-Za-z0-9\-_]{10,}',
        re.IGNORECASE
    )
    if BOT_CMD_RE.search(p_lower) or STOP_BOT_RE.search(p_lower) or API_KEY_RE.search(prompt) or KEY_VALUE_RE.search(prompt):
        return True

    return False

def split_tasks(text: str) -> list[str]:
    """Hybrid Task Decomposer (Regex + LLM Fallback approximation)."""
    # 1. Split numbered lists
    parts = re.split(r"\n?\s*(?:\d+\.|Test\s*\d+:?)\s*", text)
    # 2. Clean
    tasks = [p.strip() for p in parts if len(p.strip()) > 10]
    
    # If regex failed to split but we detect keyword 'extract all independent tasks'
    # we would call LLM. For speed, we just return the original if it didn't split well.
    if len(tasks) < 2:
        return [text]
    return tasks

executor = ThreadPoolExecutor(max_workers=5)

def run_task_sync(payload: dict):
    from backend.core.task_router import dispatch_task
    # Synchronously run the event loop dispatch
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(dispatch_task(payload))
        else:
            loop.run_until_complete(dispatch_task(payload))
    except RuntimeError:
        asyncio.run(dispatch_task(payload))

async def event_generator(
    query: str, 
    task_id: str, 
    convo_id: Optional[int] = None, 
    provider: str = "auto", 
    model: str = "",
    last_event_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    file_ids: Optional[str] = None,
    trust_mode: str = "fast"
):
    """
    V11 High-Speed Event Generator.
    - Classifies speed immediately.
    - FORCES tool-agent (complex path) if realtime data is requested.
    - Path 1/2/3: Direct LLM stream (no Redis/RQ, sub-100ms TTFT).
    - Path 4: Redis/RQ for long-running Agent tasks.
    """
    # 🚨 PRE-FLIGHT PREP (Classification & Context)
    
    # ── FIX 3: Proper Retry System ──
    try:
        if query == '{"action": "retry_task"}':
            from backend.core.task_queue import get_last_failed_task
            task = get_last_failed_task(str(convo_id) if convo_id else "local_user")
            
            if not task:
                yield f"id: 1\ndata: {json.dumps({'type': 'error', 'content': 'No task to retry'})}\n\n"
                return
                
            if task.get("status") == "completed" and task.get("result"):
                # ── FIX 5: Instant Result Cache ──
                result = task["result"]
                yield f"id: 1\ndata: {json.dumps({'type': 'token', 'content': result[:len(result)//2]})}\n\n"
                yield f"id: 2\ndata: {json.dumps({'type': 'token', 'content': result[len(result)//2:]})}\n\n"
                yield f"id: 3\ndata: {json.dumps({'type': 'final', 'content': '', 'provider': provider, 'model': model})}\n\n"
                return
                
            task["attempt"] += 1
            task["status"] = "retrying"
            query = task["query"]  # Swap back to original query for requeue
            task_id = task["task_id"]
            logger.info(f"[Retry] Requeueing task {task_id} attempt {task['attempt']}")
    except Exception as e:
        pass

    try:
        speed = classify_speed(query)
        
        # Load context early to check state
        from backend.core.context_manager import get_agent_context, build_system_prompt, update_context, save_agent_context
        pco_context = get_agent_context(user_id="local_user", bot_id="local_bot")
        
        # 🚨 STRICT ROUTING ENFORCEMENT
        from backend.builder.router import is_builder_request, is_recall_trigger
        
        # Add Task Trigger Layer
        from backend.orchestrator.priority_router import detect_intent
        fast_intent = detect_intent(query)
        if fast_intent == "builder" and not (is_recall_trigger(query) and pco_context.get("builder_preferences")):
            speed = "complex"
            
        if needs_complex_routing(query, pco_context):
            # Exception: if it's a builder recall query AND we have preferences, DO NOT route to complex.
            # Handle it instantly in the fast path to trigger the memory recall message.
            if is_recall_trigger(query) and pco_context.get("builder_preferences"):
                speed = "instant" 
            else:
                logger.info("[SSE] Complex routing detected (Realtime/Builder). Forcing full tool path.")
                speed = "complex"

        logger.info(f"[SSE] Speed={speed} | query={query[:50]}")
    except Exception as e:
        logger.error(f"[SSE] Pre-flight failed: {e}")
        yield f"id: 1\ndata: {json.dumps({'type': 'error', 'content': 'System initialization failed. Try again?'})}\n\n"
        yield f"id: 2\ndata: {json.dumps({'type': 'final', 'content': ''})}\n\n"
        return

    # ── KEY INJECTION: detect API keys in the chat message ──────────────
    if _KEY_INJECTION_AVAILABLE:
        try:
            inj = detect_and_store_keys(query)
            if inj.get("found") and inj.get("reply"):
                logger.info(f"[Chat] Key injection: stored {[f['env_var'] for f in inj['found']]}")
                # Persist user message first
                user_msg_id = await save_message_to_db(convo_id, "user", query) if convo_id else None
                if user_msg_id:
                    yield f"id: 0\ndata: {json.dumps({'type': 'user_persisted', 'msg_id': user_msg_id})}\n\n"
                # Stream key injection confirmation reply
                reply_text = inj["reply"]
                idx = 0
                for i in range(0, len(reply_text), 6):
                    idx += 1
                    yield f"id: {idx}\ndata: {json.dumps({'type': 'token', 'content': reply_text[i:i+6]})}\n\n"
                    import asyncio as _aio; await _aio.sleep(0.004)
                # Persist assistant reply
                saved_id = await save_message_to_db(convo_id, "assistant", reply_text, "key_injector", "internal") if convo_id else None
                yield f"id: {idx+1}\ndata: {json.dumps({'type': 'final', 'content': '', 'provider': 'key_injector', 'model': 'internal', 'persisted': saved_id is not None, 'msg_id': saved_id})}\n\n"
                return
        except Exception as _ki_exc:
            logger.warning(f"[Chat] Key injection check failed: {_ki_exc}")

    # Persist User message to DB synchronously to ensure order
    user_msg_id = None
    if convo_id:
        user_msg_id = await save_message_to_db(convo_id, "user", query)
        if user_msg_id:
            yield f"id: 0\ndata: {json.dumps({'type': 'user_persisted', 'msg_id': user_msg_id})}\n\n"

    # ══════════════════════════════════════════════════════════════════════════
    # ⚡ FAST PATHS (Direct Streaming)
    # ══════════════════════════════════════════════════════════════════════════
    if speed in ["instant", "fast", "simple"]:
        final_p, final_m = provider, model
        result = ""
        idx = 0

        # Sub-Path A: Instant (Templates / Memory Recall)
        if speed == "instant":
            
            # 1. Builder Preference Recall Hook
            prefs = pco_context.get("builder_preferences")
            if is_recall_trigger(query) and prefs:
                # ── Merge any NEW prefs from the current query ─────────────
                # e.g. "build website for selling mobiles" → detect "mobiles"
                from backend.builder.preference_parser import (
                    smart_parse_preferences, extract_product_type, build_prefs_summary
                )
                from backend.core.context_manager import save_agent_context
                
                parsed_new = await smart_parse_preferences(query)
                
                # Merge: new non-None values override saved prefs
                merged_prefs = prefs.copy()
                for k, v in parsed_new.items():
                    if v is not None and not k.startswith("_"):
                        merged_prefs[k] = v
                
                # Also detect product_type directly from query text
                detected_product = extract_product_type(query)
                if detected_product:
                    merged_prefs["product_type"] = detected_product
                
                # Persist the merged prefs if anything changed
                if merged_prefs != prefs:
                    pco_context["builder_preferences"] = merged_prefs
                    save_agent_context(user_id="local_user", bot_id="local_bot", context=pco_context)
                
                # Build display summary
                summary = build_prefs_summary(merged_prefs)
                
                if merged_prefs != prefs:
                    reply = (f"Updated your plan \ud83d\udc4d Here's what I've got:\n\n"
                             f"{summary}\n\n"
                             f"Ready to build or want to change anything?\n\n"
                             f"[\ud83d\udd18 Build it now](action:use this)  [\ud83d\udd18 Change something](action:no)")
                else:
                    reply = (f"I remember your preferences \ud83d\udc4d\n\n"
                             f"{summary}\n\n"
                             f"Do you want me to use this or change anything?\n\n"
                             f"[\ud83d\udd18 Use these settings](action:use this)  [\ud83d\udd18 Change everything](action:no)")
                final_p, final_m = "memory", "pco-recall"
            else:
                reply = get_instant_reply(query)
                final_p, final_m = "instant", "template"
                
            chunk_size = 4
            for i in range(0, len(reply), chunk_size):
                idx += 1
                yield f"id: {idx}\ndata: {json.dumps({'type': 'token', 'content': reply[i:i+chunk_size]})}\n\n"
                await asyncio.sleep(0.005)
            result = reply

        # Sub-Path B: Fast (Cache or Direct LLM)
        elif speed in ["fast", "simple"]:
            cache_hit = find_similar(query)
            if cache_hit:
                logger.info("[SSE] Cache HIT")
                rewritten = await rewrite_or_return(cache_hit["answer"], query, provider=provider, model=model)
                for i in range(0, len(rewritten), 6):
                    idx += 1
                    yield f"id: {idx}\ndata: {json.dumps({'type': 'token', 'content': rewritten[i:i+6]})}\n\n"
                    await asyncio.sleep(0.005)
                result = rewritten
                final_p, final_m = "cache", "semantic-rewrite"
            else:
                logger.info(f"[SSE] Direct LLM stream ({speed})")
                llm = UniversalProvider(provider=provider, model=model)
                
                system_prompt_str = build_system_prompt(pco_context)

                # Inject file contents (secure, token-budgeted)
                file_context = ""
                if file_ids:
                    try:
                        from backend.api.files import get_uploaded_file
                        from backend.services.file_processor import FileResult, build_file_context
                        ids = [fid.strip() for fid in file_ids.split(",") if fid.strip()]
                        file_results = []
                        for fid in ids:
                            payload = get_uploaded_file(fid)
                            if payload:
                                file_results.append(FileResult(
                                    file_id=payload["file_id"],
                                    filename=payload["filename"],
                                    file_type=payload["file_type"],
                                    category=payload["category"],
                                    content_text=payload["content"],
                                    raw_preview=payload.get("raw_preview", ""),
                                    metadata=payload.get("metadata", {}),
                                ))
                        if file_results:
                            file_context = build_file_context(file_results)
                    except Exception as e:
                        logger.error(f"[SSE] Failed to load file context: {e}")

                # Inject recent conversation history for context
                recent_history = ""
                if convo_id:
                    try:
                        from backend.services.conversation_service import get_messages
                        with SessionLocal() as db:
                            msgs = get_messages(db, convo_id)
                            recent_msgs = msgs[-6:] if msgs else []
                            for m in recent_msgs:
                                role_name = "Assistant" if m.role == "assistant" else "User"
                                recent_history += f"{role_name}: {m.content}\n"
                    except Exception as e:
                        logger.error(f"[SSE] Failed to load history: {e}")

                persona = get_persona_prompt(query, is_autonomous=False)
                prompt = (
                    f"{system_prompt_str}\n\n"
                    f"{file_context}\n"
                )
                if recent_history:
                    prompt += f"[Recent Conversation]:\n{recent_history}\n"
                prompt += f"User: {query}\nReply concisely."

                
                got_first = False
                try:
                    async for token in llm.astream([{"role": "user", "content": prompt}]):
                        if token and not token.startswith("Error:"):
                            idx += 1
                            got_first = True
                            result += token
                            yield f"id: {idx}\ndata: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    
                    final_p, final_m = llm.final_provider, llm.final_model
                    
                    if not result.strip():
                        # Fallback to sync if stream failed
                        result = llm.generate([{"role": "user", "content": prompt}])
                        for i in range(0, len(result), 8):
                            idx += 1
                            yield f"id: {idx}\ndata: {json.dumps({'type': 'token', 'content': result[i:i+8]})}\n\n"
                            await asyncio.sleep(0.005)

                    if result and len(result) > 5:
                        store(query, result)
                except Exception as e:
                    logger.error(f"[SSE] Direct stream failed: {e}")
                    error_msg = "Hmm, connection issues. Try again?"
                    yield f"id: {idx+1}\ndata: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
                    return

        # ── Persist BEFORE sending final event (prevents show→disappear flicker) ──
        saved_msg_id = None
        if convo_id:
            saved_msg_id = await save_message_to_db(convo_id, "assistant", result, final_p, final_m)
            if saved_msg_id:
                logger.info(f"[SSE] Assistant message persisted (msg_id={saved_msg_id}) before final event.")
            else:
                logger.warning("[SSE] Assistant message persistence failed — frontend may flicker.")
        
        # Async Context Update (PCO) — ok as background since not UI-blocking
        async def background_update_pco():
            llm_inst = UniversalProvider(provider=final_p, model=final_m)
            updated_pco = await update_context(llm_inst, pco_context, f"User: {query}\nAssistant: {result}")
            save_agent_context(user_id="local_user", bot_id="local_bot", context=updated_pco)
            
        if background_tasks:
            background_tasks.add_task(background_update_pco)

        # Send final event WITH the persisted flag so frontend knows DB is ready
        yield f"id: {idx+1}\ndata: {json.dumps({'type': 'final', 'content': '', 'provider': final_p, 'model': final_m, 'persisted': saved_msg_id is not None, 'msg_id': saved_msg_id})}\n\n"
        return

    # ══════════════════════════════════════════════════════════════════════════
    # 🧠 FULL PATH (Distributed Worker Multi-Queue)
    # ══════════════════════════════════════════════════════════════════════════
    from backend.core.task_router import dispatch_task
    
    # Always dispatch as a single task — chat_worker.background_agent_loop handles
    # multi-part queries internally with proper SSE streaming.
    # The previous executor.submit split path fired tasks with no streaming return.
    task_payload = {
        "task_id": task_id,
        "query": query,
        "file_ids": file_ids or "",
        "convo_id": str(convo_id) if convo_id else None,
        "provider": provider,
        "model": model,
        "trust_mode": trust_mode
    }
    
    # Initialize Task State
    from backend.core.task_queue import init_task_state, update_task_state
    init_task_state(task_id, query)
    
    if bool(redis_conn):
        try: redis_conn.delete(f"task:{task_id}:events")
        except: pass
    
    returned_hash = await dispatch_task(task_payload)
    if returned_hash != "duplicate":
        task_id = returned_hash


    # Monitor events
    idx: int = 0
    if last_event_id is not None:
       try:
           idx = int(last_event_id)
       except ValueError:
           pass

    # Hard fallback timeout: never poll forever. If worker is stuck/dead,
    # drain cleanly after POLL_TIMEOUT seconds.
    POLL_TIMEOUT = 180.0  # User Request: SSE_TIMEOUT = 180
    poll_start = time.time()

    while True:
        # ── Hard timeout guard (Root Cause 3: no fallback timeout) ──────────
        if time.time() - poll_start > POLL_TIMEOUT:
            logger.error(f"[SSE] Poll timeout exceeded for task {task_id}. Worker may be stuck/dead.")
            
            # FIX 3: Cache Failed Task
            from backend.core.task_queue import get_task_state, cache_last_failed_task
            task_info = get_task_state(task_id)
            if task_info:
                task_info["status"] = "failed"
                cache_last_failed_task(str(convo_id) if convo_id else "local_user", task_info)
                
            yield f"id: {idx+1}\nevent: message\ndata: {json.dumps({'type': 'error', 'content': 'Request timed out. The worker may be overloaded. Please try again.'})}\n\n"
            return

        if redis_conn:
            length = redis_conn.llen(f"task:{task_id}:events")
            if length > idx:
                events_raw = redis_conn.lrange(f"task:{task_id}:events", idx, length - 1)
                for raw in events_raw:
                    idx += 1
                    event_data = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                    yield f"id: {idx}\nevent: message\ndata: {event_data}\n\n"
                    try:
                        parsed = json.loads(event_data)
                        if parsed.get("type") in ["final", "error"]:
                            if parsed.get("type") == "final":
                                from backend.core.task_queue import update_task_state
                                update_task_state(task_id, {"status": "completed", "result": parsed.get("content", "")})
                            return
                    except: pass
        else:
            from backend.api.chat_worker import TASKS
            task_data = TASKS.get(task_id)
            if task_data:
                if task_data.get("status") == "cancelled":
                    yield f"id: {idx+1}\nevent: message\ndata: {json.dumps({'type': 'error', 'content': 'Task cancelled.'})}\n\n"
                    return
                if len(task_data["steps"]) > idx:
                    for i in range(idx, len(task_data["steps"])):
                        idx += 1
                        event = task_data["steps"][i]
                        yield f"id: {idx}\nevent: message\ndata: {json.dumps(event)}\n\n"
                        if event.get("type") in ["final", "error"]:
                            return
                elif task_data.get("status") in ["completed", "error"]:
                    return
            else:
                # Task not yet registered — check if timed out waiting for pickup
                if time.time() - poll_start > 10.0 and idx == 0:
                    logger.warning(f"[SSE] Task {task_id} not picked up after 10s. Worker may be down.")

        await asyncio.sleep(1.0)  # User Request: poll_interval = 1.0


@router.get("/stream")
async def stream(request: Request, query: str, background_tasks: BackgroundTasks):
    """
    V11 Structured SSE Endpoint with high-speed direct routing.
    - Classifies speed immediately.
    - Uses BackgroundTasks for non-blocking DB saves.
    - Bypasses RQ/Redis for fast casual paths.
    """
    # Layer 1: Advanced prompt injection detection (jailbreak, DAN, base64 payloads)
    if _USE_PI_GUARD and _pi_guard:
        is_injection, injection_labels = _pi_guard.detect_injection(query)
        if is_injection:
            return StreamingResponse(
                iter([f'data: {{"type": "error", "content": "Message blocked: prompt injection detected ({", ".join(injection_labels[:2])}). Please rephrase."}}\n\n']),
                media_type="text/event-stream"
            )

    # Layer 2: Basic content safety check
    if not is_safe(query):
        return StreamingResponse(
            iter([f'data: {{"type": "error", "content": "Message blocked by safety filter."}}\n\n']),
            media_type="text/event-stream"
        )

    # Layer 3: Rate limit (use IP as user_id until auth is added)
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate(client_ip):
        return StreamingResponse(
            iter([f'data: {{"type": "error", "content": "Rate limited. Please wait before sending another message."}}\n\n']),
            media_type="text/event-stream"
        )

    task_id = request.query_params.get("taskId")
    convo_id_str = request.query_params.get("convoId")
    provider = request.query_params.get("provider", "auto")
    model = request.query_params.get("model", "")
    file_ids = request.query_params.get("file_ids", "")
    
    convo_id = None
    if convo_id_str and convo_id_str.isdigit():
        convo_id = int(convo_id_str)
        
    if not task_id:
        task_id = str(uuid.uuid4())
        
    trust_mode = request.query_params.get("trust_mode", "fast")
    last_event_id = request.headers.get("Last-Event-ID") or request.query_params.get("last_event_id")
    return StreamingResponse(
        event_generator(
            query=query, 
            task_id=task_id, 
            convo_id=convo_id, 
            provider=provider, 
            model=model, 
            last_event_id=last_event_id, 
            background_tasks=background_tasks,
            file_ids=file_ids,
            trust_mode=trust_mode
        ),
        media_type="text/event-stream"
    )



@router.delete("/stream/{task_id}")
async def cancel_stream(task_id: str):
    """
    Cancels a running task. Sets status to 'cancelled' so the event_generator
    loop terminates and the UltraAgent cancellation flag is checked.
    """
    cancelled = False
    if redis_conn:
        status = redis_conn.get(f"task:{task_id}:status")
        if status and status.decode() == "running":
            redis_conn.set(f"task:{task_id}:status", "cancelled")
            # Push a terminal error event so any currently-connected stream drains cleanly
            redis_conn.rpush(
                f"task:{task_id}:events",
                json.dumps({"type": "error", "content": "Task was cancelled."})
            )
            cancelled = True
    else:
        from backend.api.chat_worker import TASKS
        if task_id in TASKS and TASKS[task_id].get("status") == "running":
            TASKS[task_id]["status"] = "cancelled"
            TASKS[task_id]["steps"].append({"type": "error", "content": "Task was cancelled."})
            cancelled = True

    if cancelled:
        return {"status": "cancelled", "task_id": task_id}
    return {"status": "not_found_or_already_done", "task_id": task_id}

@router.delete("/stream/context")
async def wipe_context(user_id: str = "local_user", bot_id: str = "local_bot"):
    """
    Optional User Delete Endpoint.
    Wipes the persistent context for the specified user/bot pairing.
    """
    from backend.core.context_manager import delete_agent_context
    success = delete_agent_context(user_id, bot_id)
    if success:
        return {"status": "success", "message": "Context wiped successfully."}
    return {"status": "not_found", "message": "No context found to wipe."}

# Note: The original chat.py might have had other endpoints like / (POST chat). 

# However, the user provided a full replacement for chat.py focused on streaming.
# I will check if there were other important parts.
@router.get("/resume")
async def resume_task(
    request: Request,
    task_id: str,
    resume_token: str,
    convo_id: Optional[int] = None,
    user_id: str = "local_user",
    bot_id: str = "local_bot",
    provider: str = "auto",
    model: str = "",
    trust_mode: str = "fast"
):
    """
    Resumes a task that was PAUSED for OAuth authentication.
    Validates the resume_token before continuing.
    Returns status=expired if the token window has passed.
    """
    # ── Fast path: token expiry check BEFORE opening stream ──────────────
    from backend.oauth.oauth_manager import validate_resume_token
    if not validate_resume_token(resume_token, task_id, user_id):
        return JSONResponse(
            status_code=422,
            content={
                "status": "expired",
                "action": "restart_required",
                "message": "The resume window has expired. Please start a new task."
            }
        )

    # ── Task must still exist (not yet purged by zombie cleanup) ─────────
    task_data = None
    if redis_conn:
        stored = redis_conn.get(f"task:{task_id}:state")
        if stored:
            import json as _json
            task_data = _json.loads(stored)
    
    if task_data and task_data.get("state") == "failed" and "timed out" in task_data.get("error", ""):
        return JSONResponse(
            status_code=410,
            content={
                "status": "expired",
                "action": "restart_required",
                "message": "Task was purged by the cleanup engine. Please start a new task."
            }
        )

    # ── Set up SSE generator for the resumed task ─────────────────────────
    if task_id not in TASKS:
        TASKS[task_id] = {"status": "resuming", "steps": []}

    async def resume_generator():
        from backend.orchestrator.task_controller import TaskController
        controller = TaskController(provider=provider, model=model, trust_mode=trust_mode)

        def _publish_resume(event: dict):
            TASKS[task_id]["steps"].append(event)
            if redis_conn:
                redis_conn.rpush(f"task:{task_id}:events", json.dumps(event))

        try:
            result = await controller.resume(
                task_id=task_id,
                resume_token=resume_token,
                publish=_publish_resume,
                user_id=user_id,
                bot_id=bot_id
            )

            if "⏸️" not in result and "⏳" not in result:
                TASKS[task_id]["status"] = "completed"
                _publish_resume({"type": "final", "content": "", "provider": provider, "model": model})
            elif "⏸️" in result:
                TASKS[task_id]["status"] = "paused"
            else:
                TASKS[task_id]["status"] = "retrying"

        except Exception as e:
            logger.error(f"[Resume] Error resuming task {task_id}: {e}", exc_info=True)
            _publish_resume({"type": "error", "content": str(e)})
            TASKS[task_id]["status"] = "error"

        # Stream all accumulated events back
        for event in TASKS[task_id]["steps"]:
            data = json.dumps(event)
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.005)

    return StreamingResponse(resume_generator(), media_type="text/event-stream")
