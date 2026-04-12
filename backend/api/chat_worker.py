import json
import asyncio
import logging
import uuid
import time
import re as _re
from typing import Dict, Any, Optional, List
from backend.core.task_queue import redis_conn

logger = logging.getLogger(__name__)

TASKS: Dict[str, Any] = {}
_LAST_ACTIVITY: Dict[str, float] = {}

# Keep router instance globally
_GLOBAL_ROUTER = None

# Orchestrator import
from backend.agents.ultra_agent import UltraAgent

# Register specialized tools on module load
try:
    from backend.agents.specialized.web_agent import register as _reg_web
    from backend.agents.specialized.file_agent import register as _reg_file
    _reg_web()
    _reg_file()
except Exception as _e:
    logger.warning(f"Failed to register specialized tools: {_e}")

# Fix #12: Bounded TASKS dict — evict oldest when full
TASKS: Dict[str, Dict[str, Any]] = {}
MAX_STEPS = 10
MAX_TASKS = 100  # Prevent unbounded memory growth

# ──────────────────────────────────────────────────────────────────────────────
# Capability Mapping — replaces hardcoded `if "gmail" in message` checks
# ──────────────────────────────────────────────────────────────────────────────
TOOL_PROVIDER_MAP: Dict[str, str] = {
    "send_email": "google",
    "read_email": "google",
    "search_email": "google",
    "draft_email": "google",
    "read_calendar": "google",
    "create_event": "google",
    "list_events": "google",
    "google_drive": "google",
    "upload_file": "google",
    "list_files": "google",
    "youtube_search": "google",
    "post_slack": "slack",
    "send_slack": "slack",
    "read_slack": "slack",
    "notion_page": "notion",
    "create_notion": "notion",
    "outlook_email": "microsoft",
    "teams_message": "microsoft",
    "onedrive": "microsoft",
}

# Keywords that hint at a tool need (matched against user query)
_TOOL_KEYWORD_PATTERNS = {
    "google": _re.compile(
        r'\b(gmail|send\s*email|read\s*email|draft|calendar|schedule|event|'
        r'google\s*drive|upload\s*to\s*drive|youtube)\b', _re.IGNORECASE
    ),
    "slack": _re.compile(
        r'\b(slack|post\s*to\s*slack|slack\s*message)\b', _re.IGNORECASE
    ),
    "notion": _re.compile(
        r'\b(notion|notion\s*page|create\s*notion)\b', _re.IGNORECASE
    ),
    "microsoft": _re.compile(
        r'\b(outlook|teams|onedrive|microsoft)\b', _re.IGNORECASE
    ),
}

# OAuth state tracking (per task_id)
OAUTH_STATES: Dict[str, Dict[str, Any]] = {}


def _detect_required_provider(query: str) -> Optional[str]:
    """Detect if the user's query requires a specific OAuth provider."""
    for provider, pattern in _TOOL_KEYWORD_PATTERNS.items():
        if pattern.search(query):
            return provider
    return None


# ── Task Splitter ───────────────────────────────────────────────────────────────────
MAX_SUBTASKS = 10  # Safety limit

_NUMBERED_LIST_RE = _re.compile(r"^\s*\d+[.)\-]\s+", _re.MULTILINE)


def split_tasks(text: str) -> List[str]:
    """
    Splits multi-task input into individual tasks.
    
    Handles:
      - Newline-separated tasks
      - Numbered lists: "1. task one\n2. task two"
    """
    # First try numbered list detection
    if _NUMBERED_LIST_RE.search(text):
        # Split on numbered prefixes ("1. ", "2) ", "3- " etc.)
        parts = _re.split(r"\n+\s*\d+[.)\-]\s+", text.strip())
        # The first element might be empty or a pre-amble
        tasks = [p.strip() for p in parts if p.strip()]
    else:
        # Split on blank lines or multiple newlines
        tasks = [p.strip() for p in _re.split(r"\n{2,}", text.strip()) if p.strip()]

    # If only one task detected, return as-is (no splitting needed)
    if len(tasks) <= 1:
        return [text.strip()]

    # Apply safety limit
    return tasks[:MAX_SUBTASKS]


def _check_oauth_needed(
    query: str, user_id: str, bot_id: str, task_id: str, save_step_fn
) -> bool:
    """
    Check if the query requires an OAuth-connected provider.
    If so and the token is missing, emit a structured oauth_connect event
    and return True (caller should stop processing).
    """
    provider = _detect_required_provider(query)
    if not provider:
        return False

    try:
        from backend.oauth.oauth_manager import has_token
        if has_token(user_id, bot_id, provider):
            return False  # Token exists — proceed normally
    except Exception as e:
        logger.warning(f"[OAuth Check] Could not verify token: {e}")
        return False  # Don't block on check failure

    # Token missing — emit structured payload for frontend
    import os
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8001")
    connect_url = (
        f"{backend_url}/api/v1/oauth/{provider}/connect"
        f"?user_id={user_id}&bot_id={bot_id}"
    )

    oauth_event = {
        "type": "oauth_connect",
        "provider": provider,
        "url": connect_url,
        "button_text": f"Connect {provider.capitalize()}",
    }
    save_step_fn(oauth_event)

    # Track state
    OAUTH_STATES[task_id] = {
        "user_id": user_id,
        "bot_id": bot_id,
        "provider": provider,
        "status": "pending",
    }

    # Also emit a friendly text message
    save_step_fn({
        "type": "token",
        "content": (
            f"🔗 To use {provider.capitalize()} features, you need to connect your account first. "
            f"Click the button above to authorize access."
        ),
    })
    save_step_fn({"type": "final", "content": ""})

    logger.info(f"[OAuth Check] Emitted oauth_connect for provider={provider} user={user_id}")
    return True


def _evict_old_tasks():
    """Remove oldest task when TASKS exceeds MAX_TASKS."""
    if len(TASKS) >= MAX_TASKS:
        oldest_key = next(iter(TASKS))
        del TASKS[oldest_key]

async def background_agent_loop(
    query: str,
    task_id: str,
    convo_id: Optional[str] = None,
    provider: str = "auto",
    model: str = "",
    user_id: str = "local_user",
    bot_id: str = "local_bot",
    file_ids: str = "",
):
    """
    This function runs inside the RQ worker (or synchronously on Windows).
    user_id / bot_id are needed for scoped OAuth token lookups.
    """
    logger.info(f"Starting background_agent_loop for task {task_id} (convo: {convo_id})")
    
    import re
    import os
    import hashlib
    import time
    import json
    from pathlib import Path

    # ── Idempotency Check ──────────────────────────────────────────────────
    # Prevents rapid double-click executions using a short TTL
    idem_key = hashlib.sha256(f"idem:{user_id}:{query}".encode()).hexdigest()[:16]
    
    if redis_conn:
        # Use set with NX=True (only set if not exists) and EX=15s (expire after 15s)
        acquired = redis_conn.set(f"idem:{idem_key}", task_id, nx=True, ex=20)
        if not acquired:
            logger.warning(f"Dropping duplicate execution for query '{query[:20]}' (Idempotency Key: {idem_key})")
            error_event = {"type": "error", "content": "Duplicate request detected. Please wait for the previous execution to finish."}
            redis_conn.rpush(f"task:{task_id}:events", json.dumps(error_event))
            redis_conn.set(f"task:{task_id}:status", "error")
            return

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
        r'(gemini|openai|tavily|anthropic)[^:]*:\s*([A-Za-z0-9\-\_:]+)',
        re.IGNORECASE
    )

    stop_match = STOP_BOT_RE.search(query)
    bot_match = BOT_CMD_RE.search(query) if not stop_match else None
    api_match = API_KEY_RE.search(query) if not bot_match and not stop_match else None

    # 1. Handle Stop Bot Command
    if stop_match:
        from backend.api.integrations import _stop_bot, RUNNING_BOTS
        platform = stop_match.group(1).lower()
        
        target_bot_id = None
        for bid, info in RUNNING_BOTS.items():
            if info.get("platform") == platform or bid == platform:
                target_bot_id = bid
                break
                
        result = _stop_bot(target_bot_id) if target_bot_id else {"error": "Not running"}
        
        if "error" in result:
            bot_reply = f"ℹ️ The {platform.capitalize()} bot is not currently running."
        else:
            bot_reply = f"🛑 {platform.capitalize()} bot has been successfully stopped."

        try:
            from backend.core.database import SessionLocal
            from backend.services import conversation_service
            db = SessionLocal()
            conversation_service.create_message(db, int(convo_id), "assistant", bot_reply)
            db.close()
        except:
            pass
        return bot_reply

    # 2. Handle Start Bot Command
    if bot_match:
        platform = bot_match.group(1).lower()
        token = bot_match.group(2).strip()
        env_key = f"{platform.upper()}_BOT_TOKEN"

        # 1. Update environment and .env file
        os.environ[env_key] = token
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            current = env_path.read_text()
            if env_key in current:
                lines = [f"{env_key}={token}" if line.startswith(f"{env_key}=") else line for line in current.splitlines()]
                env_path.write_text("\n".join(lines) + "\n")
            else:
                with env_path.open("a") as f:
                    f.write(f"\n{env_key}={token}\n")
        else:
            env_path.write_text(f"{env_key}={token}\n")

        logger.info(f"[Bot-Cmd] Launching {platform} bot with token {token[:12]}...")

        from backend.api.integrations import _start_bot
        from backend.services.bot_service import create_bot
        from backend.core.database import SessionLocal
        db = SessionLocal()
        try:
            bot = create_bot(db, name=f"{platform.capitalize()} Bot", platform=platform, token=token, personality=query)
            bot_id = bot.id
        finally:
            db.close()

        result = _start_bot(platform, token, bot_id=bot_id)

        # 3. Build a human-friendly response
        if result.get("started"):
            bot_reply = (
                f"✅ **{platform.capitalize()} bot started successfully!**\n\n"
                f"• Token: `{token[:12]}...`\n"
                f"• PID: `{result.get('pid')}`\n"
                f"• Status: Running\n\n"
                f"Your bot is now live on {platform.capitalize()}. "
                f"Send `/start` to your bot to confirm it's working."
            )
        elif result.get("already_running"):
            bot_reply = (
                f"ℹ️ **{platform.capitalize()} bot is already running.**\n\n"
                f"If you want to restart it with a new token, stop it first from the Settings → Bot Tokens tab."
            )
        else:
            error = result.get("error", "Unknown error")
            bot_reply = (
                f"❌ **Failed to start {platform.capitalize()} bot.**\n\n"
                f"Error: {error}\n\n"
                f"Make sure `{platform}_bot.py` exists in the project root."
            )

        _evict_old_tasks()
        TASKS[task_id] = {"status": "completed", "steps": []}
        step_event = {"type": "final", "content": bot_reply}
        TASKS[task_id]["steps"].append(step_event)
        if redis_conn:
            redis_conn.rpush(f"task:{task_id}:events", json.dumps(step_event))
            redis_conn.set(f"task:{task_id}:status", "completed")
        logger.info(f"[Bot-Cmd] Done — {platform} bot result: {result}")
        return  # ← skip LLM entirely

    elif api_match:
        # Legacy: save API key only (no bot start)
        platform = api_match.group(1).lower()
        key_value = api_match.group(2).strip()
        env_key = f"{platform.upper()}_API_KEY"
        os.environ[env_key] = key_value
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            current = env_path.read_text()
            if env_key in current:
                lines = [f"{env_key}={key_value}" if line.startswith(f"{env_key}=") else line for line in current.splitlines()]
                env_path.write_text("\n".join(lines) + "\n")
            else:
                with env_path.open("a") as f:
                    f.write(f"\n{env_key}={key_value}\n")
        logger.info(f"[Fast-Path] Bootstrapped {env_key}")

    # ── Orchestrator Pipeline ───────────────────────────────────────────────
    from backend.orchestrator import (
        TaskContext, TaskState, ExecutionDispatcher
    )
    from backend.core.context_manager import get_agent_context
    
    global _GLOBAL_ROUTER
    if "_GLOBAL_ROUTER" not in globals() or _GLOBAL_ROUTER is None:
        from backend.orchestrator import HybridRouter, CachedRouter
        _GLOBAL_ROUTER = CachedRouter(HybridRouter())
    
    # Setup TASKS container for SSE fallback
    _evict_old_tasks()
    TASKS[task_id] = {"status": "running", "steps": [], "step": 0}

    def _save_step(event: Dict[str, Any]):
        if task_id not in TASKS:
            TASKS[task_id] = {"status": "running", "steps": []}
        TASKS[task_id]["steps"].append(event)
        if redis_conn:
            redis_conn.rpush(f"task:{task_id}:events", json.dumps(event))

    # 1. Setup Task State Machine
    task_ctx = TaskContext(task_id, user_id=user_id, redis_conn=redis_conn)
    task_ctx.transition(TaskState.ROUTING)
    
    # ── OAuth Capability Gate ────────────────────────────────────────────────
    if _check_oauth_needed(query, user_id, bot_id, task_id, _save_step):
        task_ctx.transition(TaskState.COMPLETED)
        TASKS[task_id]["status"] = "completed"
        return

    # ── Multi-Task Splitting ────────────────────────────────────────────────
    sub_tasks = split_tasks(query)
    is_multi_task = len(sub_tasks) > 1

    # Detect execution mode (if user says 'chain', or 'then', or 'summarize it')
    mode = "chain" if any(kw in query.lower() for kw in ["chain", "then ", "summarize it"]) else "parallel"

    if is_multi_task:
        logger.info(f"[ChatWorker] Multi-task detected: {len(sub_tasks)} sub-tasks for task {task_id} (Mode: {mode})")
        _save_step({
            "type": "step",
            "content": f"🧩 Detected {len(sub_tasks)} tasks — processing in **{mode}** mode...",
            "agent": "controller"
        })

    # 2. Dispatch via Central Task Controller (The Brain)
    from backend.orchestrator.task_controller import TaskController
    controller = TaskController(provider=provider, model=model)
    
    all_results = []
    
    def trim_context(text: str, max_chars: int = 1000) -> str:
        if not text:
            return ""
        return text if len(text) <= max_chars else text[:max_chars] + "\n...[truncated]"

    previous_output = ""

    try:
        for i, sub_query in enumerate(sub_tasks):
            effective_query = sub_query
            if is_multi_task:
                if mode == "chain" and previous_output:
                    effective_query = f"Context from previous task:\n{previous_output}\n\nCurrent Task:\n{sub_query}"
                _save_step({
                    "type": "step",
                    "content": f"🔹 Task {i+1}/{len(sub_tasks)}: {sub_query[:80]}...",
                    "agent": "controller"
                })

            from backend.orchestrator.priority_router import detect_intent
            intent = detect_intent(effective_query)
            
            if intent == "builder":
                from backend.builder.multi_agent_builder import multi_agent_build
                from backend.core.context_manager import get_agent_context
                
                context = get_agent_context(user_id=user_id, bot_id=bot_id)
                prefs = context.get("builder_preferences", {})
                
                files, spec = await multi_agent_build(
                    user_request=effective_query,
                    prefs=prefs,
                    provider=provider,
                    model=model,
                    publish_event=_save_step
                )
                
                md_response = "🚀 **Builder Pipeline Complete!**\n\nHere are your generated files:\n\n"
                for fname, content in files.items():
                    ext = fname.split('.')[-1]
                    md_response += f"### {fname}\n```{ext}\n{content}\n```\n\n"
                result = md_response
            else:
                result = await controller.run(
                    query=effective_query,
                    task_id=task_id,
                    publish=_save_step,
                    bot_id=bot_id,
                    user_id=user_id,
                    file_ids=file_ids
                )
            
            all_results.append(result)
            previous_output = trim_context(result)

        # Combine results for multi-task
        if is_multi_task:
            combined = "\n\n---\n\n".join(
                f"**Task {i+1}:** {sub_tasks[i]}\n\n{res}"
                for i, res in enumerate(all_results)
                if res
            )
            result = combined
        else:
            result = all_results[0] if all_results else ""
        
        # Stream the final result as tokens if the agent didn't stream inline
        if result and not any(s.get("type") == "token" for s in TASKS[task_id]["steps"]):
            for i in range(0, len(result), 8):
                _save_step({"type": "token", "content": result[i:i+8]})
                await asyncio.sleep(0.01)

        # Handle DB saving for standard chat paths
        saved_msg_id = None
        if result and convo_id:
            from backend.core.database import SessionLocal
            from backend.services import conversation_service
            with SessionLocal() as db:
                msg = conversation_service.create_message(db, int(convo_id), "assistant", result, provider=provider, model=model)
                if msg:
                    saved_msg_id = msg.id
                
        # Handle Semantic Cache (if applicable)
        if result and len(result) > 20:
            from backend.core.semantic_cache import store
            store(query, result)

        TASKS[task_id]["status"] = "completed"
        _save_step({
            "type": "final", 
            "content": "", 
            "provider": provider, 
            "model": model,
            "persisted": saved_msg_id is not None,
            "msg_id": saved_msg_id
        })

    except Exception as e:
        logger.error(f"[ChatWorker] Dispatcher failed for {task_id}: {e}", exc_info=True)
        _save_step({"type": "error", "content": str(e)})
        if task_ctx.state != TaskState.FAILED:
            task_ctx.transition(TaskState.FAILED)
        TASKS[task_id]["status"] = "error"
        
    logger.info(f"Finished background_agent_loop for task {task_id}")
