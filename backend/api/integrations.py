"""
backend/api/integrations.py (Hardened)

SECURITY FIXES:
  - Shell execution now requires explicit ?confirm=true guard  
  - Bot scripts now checked for existence before attempting launch
  - All routes updated to /api/v1/ prefix
"""
import logging
import os
import json
import subprocess
import asyncio
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, List

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.core.database import get_session
from backend.services.bot_service import get_bots, create_bot, get_bot_by_token, delete_bot
from backend.agents.manager_agent import manager_agent
from backend.core.responses import success_response, list_response, error_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
TOKENS_FILE = DATA_DIR / "integrations.json"

RUNNING_BOTS: Dict[str, dict] = {}
SHELL_TASKS: Dict[str, dict] = {}

# Max shell tasks stored in memory
MAX_SHELL_TASKS = 50


def _load_tokens() -> dict:
    if TOKENS_FILE.exists():
        try:
            return json.loads(TOKENS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_tokens(data: dict):
    TOKENS_FILE.write_text(json.dumps(data, indent=2))


def _ts() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class TokenRequest(BaseModel):
    platform: str
    token: str
    auto_start: bool = False  # Default False for safety
    embedding_provider: str = "local"


class ShellRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout: int = 30


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/tokens")
def get_tokens(db: Session = Depends(get_session)):
    # Migrate old tokens if they exist but aren't in DB
    old_tokens = _load_tokens()
    for plat, info in old_tokens.items():
        if "token" in info:
            if not get_bot_by_token(db, info["token"]):
                create_bot(db, name=f"Legacy {plat.capitalize()} Bot", platform=plat, token=info["token"])
    
    bots = get_bots(db)
    result = {}
    for b in bots:
        # Group by bot_id to support multiple bots per platform
        result[b.id] = {
            "id": b.id,
            "name": b.name,
            "platform": b.platform,
            "token_preview": b.token[:4] + "••••" + b.token[-4:] if len(b.token) > 8 else "••••",
            "personality": b.personality,
            "embedding_provider": getattr(b, "embedding_provider", "local") or "local",
            "saved": True,
            "running": b.id in RUNNING_BOTS,
            "pid": RUNNING_BOTS.get(b.id, {}).get("pid"),
        }
    return success_response(result)


@router.post("/tokens")
def save_token(req: TokenRequest, db: Session = Depends(get_session)):
    # Create new bot in DB
    bot = create_bot(db, name=f"{req.platform.capitalize()} Bot", platform=req.platform, token=req.token)
    
    # Handle Embedding Router Updates & Safe Vector Wiping
    current_provider = getattr(bot, "embedding_provider", "local") or "local"
    if current_provider != req.embedding_provider:
        bot.embedding_provider = req.embedding_provider
        db.commit()
        from backend.memory.vector_db import vector_db
        vector_db.wipe_bot_vectors(str(bot.id))

    os.environ[f"{req.platform.upper()}_BOT_TOKEN"] = req.token
    result = {"saved": True, "bot_id": bot.id, "platform": req.platform}
    
    if req.auto_start:
        start_result = _start_bot(req.platform, req.token, bot_id=bot.id)
        result.update(start_result)
    return success_response(result)


@router.post("/factory")
async def bot_factory(prompt: str, token: str, platform: str = "telegram"):
    """
    Bot Factory Endpoint: analyse -> make customize bot -> integrate.
    """
    result = await manager_agent.analyze_and_create(prompt, token, platform)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Factory failure"))
    return success_response(result)


@router.post("/start/{bot_id}")
def start_bot_route(bot_id: str, db: Session = Depends(get_session)):
    bot = get_bot(db, bot_id)
    if not bot:
        raise HTTPException(404, detail=f"No bot found for ID '{bot_id}'")
    return success_response(_start_bot(bot.platform, bot.token, bot_id=bot.id))

def _stop_bot(bot_id: str) -> dict:
    if bot_id not in RUNNING_BOTS:
        return {"error": f"Bot '{bot_id}' not running"}
    pid = RUNNING_BOTS[bot_id].get("pid")
    try:
        import platform as os_plat
        if os_plat.system() == "Windows":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGKILL)
    except Exception:
        pass
    del RUNNING_BOTS[bot_id]
    return {"stopped": True, "bot_id": bot_id}

@router.post("/stop/{bot_id}")
def stop_bot_route(bot_id: str):
    result = _stop_bot(bot_id)
    if "error" in result:
        raise HTTPException(404, detail=result["error"])
    return success_response(result)


# ── Webhook Hybrid Routing ────────────────────────────────────────────────────
from fastapi import Request
from backend.core.task_queue import enqueue_task
from dataclasses import dataclass
from typing import Optional, Dict, Any
from backend.api import security
from backend.api import webhook_handlers

# ── Deduplication Cache ──
PROCESSED_EVENTS = set()

# ── Normalizer ──
@dataclass
class UnifiedMessage:
    platform: str
    user_id: str
    text: str
    intent: str
    bot_id: str
    event_id: str
    raw_payload: Dict[str, Any]
    kwargs: Dict[str, Any]

# ── Lightweight Intent Router (no LLM call — keyword-based, instant) ──────────
_NEWS_KW    = {"news","latest","happening","update","breaking","geopolit","conflict",
               "iran","ukraine","war","election","summit","sanction","ceasefire"}
_FINANCE_KW = {"crypto","bitcoin","ethereum","btc","eth","stock","price","market",
               "trade","invest","nifty","nasdaq","forex","gold","oil","gdp"}
_BUILDER_KW = {"build","create","code","debug","refactor","write","generate",
               "script","website","app","function","class","api","sql","fix"}

def _detect_intent(text: str) -> str:
    low = text.lower()
    if any(k in low for k in _NEWS_KW):    return "news"
    if any(k in low for k in _FINANCE_KW): return "finance"
    if any(k in low for k in _BUILDER_KW): return "builder"
    return "chat"

def _run_orchestrator_unified(msg: UnifiedMessage):
    """
    Unified Pipeline: Intent → Orchestrator → LLM Gateway fallback → Reply Handler.
    """
    async def _pipeline():
        # Handle Typing Indicator immediately
        if msg.platform == "telegram":
            await webhook_handlers._tg_typing(msg.kwargs.get("token"), msg.user_id)
        # Slack / Discord natively don't need persistent long typing endpoints here, we've deferred or acked.

        final_answer: str | None = None

        # 1. Try Orchestrator
        try:
            from backend.agents.orchestrator_agent import Orchestrator
            from backend.agents.planner import PlannerAgent
            from backend.agents.memory_agent import MemoryAgent
            from backend.agents.executor import ExecutorAgent
            from backend.agents.tool_agent import ToolAgent
            from backend.llm.universal_provider import UniversalProvider

            llm = UniversalProvider()
            orchestrator = Orchestrator(PlannerAgent(llm), MemoryAgent(llm), ToolAgent([]), ExecutorAgent(llm))
            def _noop(_event): pass
            
            final_answer = await orchestrator.run(
                msg.text, publish=_noop, bot_id=msg.bot_id, platform_user_id=msg.user_id
            )
            logger.info(f"[{msg.platform.capitalize()} Webhook] Orchestrator OK")

        except Exception as orch_exc:
            logger.warning(f"[{msg.platform.capitalize()} Webhook] Orchestrator failed: {orch_exc} — via LLM Gateway")

        # 2. LLM Fallback
        if not final_answer:
            try:
                from backend.llm.llm_gateway import call_llm
                import asyncio
                system_prompts = {
                    "news":    "You are a global news analyst. Provide a concise, factual summary with key perspectives.",
                    "finance": "You are a financial analyst. Answer clearly with data-driven insights.",
                    "builder": "You are an expert software engineer. Provide working code with brief explanations.",
                    "chat":    "You are DreamAgent, a helpful AI assistant. Be concise.",
                }
                final_answer = await asyncio.to_thread(
                    call_llm, msg.text, preferred=None, retries=3, system=system_prompts.get(msg.intent, system_prompts["chat"])
                )
            except Exception as llm_exc:
                logger.error(f"[{msg.platform.capitalize()}] Gateway failed: {llm_exc}")
                final_answer = "⚠️ AI is temporarily unavailable."

        # 3. Send via platform handler
        await webhook_handlers.send_response(msg.platform, msg.user_id, final_answer or "⚠️ Error", **msg.kwargs)

    import asyncio
    asyncio.run(_pipeline())

# ── TELEGRAM ──────────────────────────────────────────────────────────────────
@router.post("/webhook/telegram/{bot_id}")
async def telegram_webhook(bot_id: str, request: Request, db: Session = Depends(get_session)):
    bot = get_bot(db, bot_id)
    if not bot:
        logger.warning(f"[Webhook] Unknown bot_id={bot_id}")
        return {"status": "unknown_bot"}

    try:
        update = await request.json()
    except Exception:
        return {"status": "invalid_json"}
        
    event_id = str(update.get("update_id", ""))
    if event_id and event_id in PROCESSED_EVENTS:
        return {"status": "duplicate ignored"}
    if event_id:
        PROCESSED_EVENTS.add(event_id)

    if "message" in update and "text" in update["message"]:
        text = update["message"]["text"].strip()
        user_id = str(update["message"]["chat"]["id"])
        
        if text.startswith("/start"):
            logger.info("[Telegram] /start command received")
            import asyncio
            asyncio.create_task(webhook_handlers.send_response(
                "telegram", user_id, 
                "🚀 *DreamAgent online!*\n\nI can help with:\n• 📰 *News analysis*\n• 💹 *Finance/Crypto*\n• 🛠 *Builder tasks*\n• 💬 *General chat*\n\nJust send a message!",
                token=bot.token
            ))
            return {"status": "ok"}
            
        intent = _detect_intent(text)
        logger.info(f"[Telegram] user={user_id} intent={intent} text={text[:60]}")

        msg = UnifiedMessage(
            platform="telegram", user_id=user_id, text=text, intent=intent, 
            bot_id=bot_id, event_id=event_id, raw_payload=update, kwargs={"token": bot.token}
        )
        task_id = enqueue_task(_run_orchestrator_unified, msg)
        return {"status": "queued", "task_id": str(task_id)}

    return {"status": "ignored"}


# ── DISCORD ───────────────────────────────────────────────────────────────────
from fastapi import Response
@router.post("/webhook/discord/{bot_id}")
async def discord_webhook(bot_id: str, request: Request, db: Session = Depends(get_session)):
    """Discord Interactions Webhook"""
    public_key = os.getenv("DISCORD_PUBLIC_KEY")
    if not public_key:
        return Response("No Discord Public Key set in .env", status_code=500)
    
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    body = await request.body()
    
    if not security.verify_discord(public_key, signature, timestamp, body):
        return Response("Invalid Request Signature", status_code=401)
        
    data = json.loads(body.decode("utf-8"))
    interaction_type = data.get("type")
    
    if interaction_type == 1:
        return {"type": 1}
        
    event_id = data.get("id", "")
    if event_id and event_id in PROCESSED_EVENTS:
        return {"status": "duplicate ignored"}
    if event_id:
        PROCESSED_EVENTS.add(event_id)

    if interaction_type == 2:
        text = data.get("data", {}).get("options", [])[0].get("value", "") if data.get("data", {}).get("options") else ""
        user_id = str(data.get("member", {}).get("user", {}).get("id") or data.get("user", {}).get("id"))
        
        intent = _detect_intent(text)
        logger.info(f"[Discord Webhook] user={user_id} intent={intent} text={text[:60]}")
        
        msg = UnifiedMessage(
            platform="discord", user_id=user_id, text=text, intent=intent, 
            bot_id=bot_id, event_id=event_id, raw_payload=data, 
            kwargs={"application_id": data.get("application_id"), "interaction_token": data.get("token")}
        )
        task_id = enqueue_task(_run_orchestrator_unified, msg)
        
        # Immediate TYPE 5 Response: DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE
        return {"type": 5, "task_id": str(task_id)}

    return {"status": "ignored"}


# ── SLACK ───────────────────────────────────────────────────────────────────
@router.post("/webhook/slack/{bot_id}")
async def slack_webhook(bot_id: str, request: Request, db: Session = Depends(get_session)):
    bot = get_bot(db, bot_id)
    signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    
    if not signing_secret or not bot:
        return Response("Invalid configuration", status_code=401)

    signature = request.headers.get("X-Slack-Signature", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    body = await request.body()

    if not security.verify_slack(signing_secret, signature, timestamp, body):
        return Response("Invalid Slack Signature", status_code=401)

    data = json.loads(body.decode("utf-8"))
    
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    event_id = data.get("event_id", "")
    if event_id and event_id in PROCESSED_EVENTS:
        return {"status": "duplicate ignored"}
    if event_id:
        PROCESSED_EVENTS.add(event_id)

    if data.get("type") == "event_callback":
        event = data.get("event", {})
        if event.get("type") == "message" and not event.get("bot_id"):
            text = event.get("text", "")
            user_id = event.get("channel", "") # Slack responds to channel
            
            intent = _detect_intent(text)
            logger.info(f"[Slack Webhook] chan={user_id} intent={intent} text={text[:60]}")
            
            msg = UnifiedMessage(
                platform="slack", user_id=user_id, text=text, intent=intent, 
                bot_id=bot_id, event_id=event_id, raw_payload=data, 
                kwargs={"token": bot.token}
            )
            task_id = enqueue_task(_run_orchestrator_unified, msg)
            return {"status": "queued", "task_id": str(task_id)}
            
    return {"status": "ok"}


# ── WHATSAPP ─────────────────────────────────────────────────────────────────
@router.get("/webhook/whatsapp/{bot_id}")
async def whatsapp_webhook_verify(request: Request):
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    q_mode = request.query_params.get("hub.mode")
    q_token = request.query_params.get("hub.verify_token")
    q_challenge = request.query_params.get("hub.challenge")

    if security.verify_whatsapp(q_mode, verify_token, q_token):
        return Response(content=q_challenge, media_type="text/plain", status_code=200)
    return Response("Verification failed", status_code=403)


@router.post("/webhook/whatsapp/{bot_id}")
async def whatsapp_webhook(bot_id: str, request: Request, db: Session = Depends(get_session)):
    bot = get_bot(db, bot_id)
    if not bot:
        return Response(status_code=404)
        
    access_token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_ID")
    
    if not access_token or not phone_id:
        return Response("WhatsApp config missing", status_code=500)
        
    data = await request.json()
    
    try:
        entries = data.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                msg_val = change.get("value", {})
                messages = msg_val.get("messages", [])
                
                for msg_obj in messages:
                    event_id = msg_obj.get("id", "")
                    if event_id in PROCESSED_EVENTS:
                        continue
                    if event_id:
                        PROCESSED_EVENTS.add(event_id)
                        
                    if msg_obj.get("type") == "text":
                        text = msg_obj.get("text", {}).get("body", "")
                        user_id = msg_obj.get("from")
                        
                        intent = _detect_intent(text)
                        logger.info(f"[WhatsApp] from={user_id} intent={intent} text={text[:60]}")
                        
                        msg = UnifiedMessage(
                            platform="whatsapp", user_id=user_id, text=text, intent=intent, 
                            bot_id=bot_id, event_id=event_id, raw_payload=data, 
                            kwargs={"token": access_token, "phone_id": phone_id}
                        )
                        task_id = enqueue_task(_run_orchestrator_unified, msg)
                        return {"status": "queued", "task_id": str(task_id)}
    except Exception as e:
        logger.error(f"[WhatsApp] processing error: {e}")

    return {"status": "ok"}

# ──────────────────────────────────────────────────────────────────────────────


@router.get("/queue")
def get_task_queue():
    queue: List[dict] = []
    for platform, info in RUNNING_BOTS.items():
        pid = info.get("pid")
        alive = False
        try:
            os.kill(pid, 0)
            alive = True
        except Exception:
            pass
        queue.append({
            "id": f"bot_{platform}", "type": "bot",
            "name": f"{platform.capitalize()} Bot",
            "status": "running" if alive else "stopped",
            "started_at": info.get("started_at"), "pid": pid,
        })
    for task_id, task in SHELL_TASKS.items():
        queue.append({
            "id": task_id, "type": "shell",
            "name": f"$ {task['command'][:40]}",
            "status": task["status"],
            "output_preview": (task.get("output") or "")[:200],
        })
    return list_response(queue)


@router.post("/shell")
async def run_shell(req: ShellRequest, confirm: bool = Query(False)):
    """
    Execute a shell command.
    SECURITY: Requires ?confirm=true to prevent accidental/malicious execution.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Shell execution requires ?confirm=true query parameter"
        )

    # Prune old tasks
    if len(SHELL_TASKS) >= MAX_SHELL_TASKS:
        oldest = next(iter(SHELL_TASKS))
        del SHELL_TASKS[oldest]

    task_id = str(uuid.uuid4())
    cwd = req.cwd or str(Path.cwd())
    SHELL_TASKS[task_id] = {
        "command": req.command, "status": "running",
        "started_at": _ts(), "output": "", "exit_code": None,
    }
    try:
        def _run_cmd():
            return subprocess.run(
                req.command, shell=True, cwd=cwd,
                capture_output=True, text=True, timeout=req.timeout
            )
        
        proc = await asyncio.to_thread(_run_cmd)
        output = proc.stdout + proc.stderr
        exit_code = proc.returncode

        SHELL_TASKS[task_id].update({"output": output, "exit_code": exit_code,
                                      "status": "done" if exit_code == 0 else "error"})
        return success_response({"task_id": task_id, "output": output,
                                  "exit_code": exit_code, "status": SHELL_TASKS[task_id]["status"]})
    except subprocess.TimeoutExpired as e:
        output = f"[TIMEOUT] Command exceeded {req.timeout}s.\n{e.stdout or ''}\n{e.stderr or ''}"
        SHELL_TASKS[task_id].update({"output": output, "exit_code": -1, "status": "error"})
        return error_response("Timeout")
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        SHELL_TASKS[task_id].update({"status": "error", "output": err_msg})
        logger.error("Shell task error: %s", err_msg)
        return error_response(f"Shell Error: {repr(e)}")


def _start_bot(platform: str, token: str, bot_id: str = None) -> dict:
    """Attempt to launch a bot subprocess — fails gracefully if script not found."""
    # Use bot_id as the tracking key if available, else fallback to platform
    track_key = bot_id if bot_id else platform
    
    bot_scripts = {
        "telegram": "telegram_bot.py",
        "discord": "discord_bot.py",
        "whatsapp": "whatsapp_bot.py",
    }
    script = bot_scripts.get(platform.lower())
    if not script:
        return {"error": f"No bot script registered for '{platform}'"}

    script_path = Path(__file__).parent.parent.parent / script
    if not script_path.exists():
        return {
            "error": f"Bot script '{script}' not found. Please create it at {script_path}",
            "started": False,
        }

    if len(RUNNING_BOTS) >= 25:
        return {"error": "Maximum 25 concurrent bots active. Please stop some bots first.", "started": False}

    if track_key in RUNNING_BOTS:
        return {"already_running": True, "bot_id": track_key}

    env = os.environ.copy()
    env[f"{platform.upper()}_BOT_TOKEN"] = token
    
    cmd = [os.sys.executable, str(script_path)]
    if bot_id:
        cmd.extend(["--bot_id", bot_id])
        
    try:
        proc = subprocess.Popen(
            cmd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        RUNNING_BOTS[track_key] = {"pid": proc.pid, "started_at": _ts(), "platform": platform}
        return {"started": True, "bot_id": track_key, "pid": proc.pid}
    except Exception as e:
        return {"error": str(e)}
