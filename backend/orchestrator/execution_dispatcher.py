"""
backend/orchestrator/execution_dispatcher.py

Central dispatch layer: takes a RouteDecision and delegates
to the correct agent/subsystem.  This is the missing link between
routing and execution — prevents logic from leaking into chat_worker.py.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from backend.orchestrator.intent_router import RouteDecision
from backend.orchestrator.task_state import TaskContext, TaskState
from backend.orchestrator.retry import with_retry, get_max_retries
from backend.orchestrator.observability import TaskLogger

logger = logging.getLogger(__name__)

# ── GC-safe task tracking with bounded size ──────────────────────────────
# asyncio tasks are GC'd if not referenced; we keep strong refs here.
# Tasks are cleaned up via done_callback — no manual eviction needed.
RUNNING_TASKS: Dict[str, asyncio.Task] = {}
JOB_STATUS: Dict[str, str] = {}  # job_id -> "running" | "done" | "error"
_MAX_JOB_HISTORY = 200  # cap history to prevent unbounded growth


def _cleanup_job(job_id: str) -> None:
    """Called via task.add_done_callback — auto-removes completed tasks."""
    RUNNING_TASKS.pop(job_id, None)
    # Keep JOB_STATUS for status queries, but cap the dict size
    if len(JOB_STATUS) > _MAX_JOB_HISTORY:
        oldest = next(iter(JOB_STATUS))
        JOB_STATUS.pop(oldest, None)
    logger.debug("[Dispatcher] Cleaned up job %s", job_id)


class ExecutionDispatcher:
    """
    Routes a RouteDecision to the correct execution path.

    Architecture:
        HybridRouter → RouteDecision → ExecutionDispatcher → Agent
    """

    def __init__(
        self,
        provider: str = "auto",
        model: str = "",
        user_id: str = "local_user",
        bot_id: str = "local_bot",
    ):
        self._provider = provider
        self._model = model
        self._user_id = user_id
        self._bot_id = bot_id

    async def dispatch(
        self,
        route: RouteDecision,
        query: str,
        task_ctx: TaskContext,
        publish: Callable[[Dict[str, Any]], None],
        convo_id: Optional[str] = None,
    ) -> str:
        """
        Execute the routed intent.

        Args:
            route:    The RouteDecision from the router.
            query:    Original user message.
            task_ctx: Task lifecycle tracker.
            publish:  SSE event publisher.
            convo_id: Conversation ID for DB persistence.

        Returns:
            Final response string.
        """
        tlog = TaskLogger(task_ctx.task_id, task_ctx.user_id)
        intent = route.intent
        max_retries = get_max_retries(intent)
        task_ctx.max_retries = max_retries
        task_ctx.route_decision = route

        tlog.info(f"Dispatching intent={intent} confidence={route.confidence:.2f}", stage="dispatch")

        # ── News intent ────────────────────────────────────────────────
        if intent == "news":
            return await self._handle_news(query, task_ctx, publish)

        # ── Builder intents ──────────────────────────────────────────────
        if intent == "builder":
            return await self._handle_builder(query, task_ctx, publish)

        if intent == "update":
            session_id = route.metadata.get("session_id", "")
            return await self._handle_update(query, session_id, task_ctx, publish)

        if intent == "continue":
            return await self._handle_continue(query, task_ctx, publish)

        # ── Autonomous mode ──────────────────────────────────────────────
        if intent == "autonomous":
            return await self._handle_autonomous(query, task_ctx, publish, convo_id)
            
        # ── Debate Engine ────────────────────────────────────────────────
        if intent == "debate":
            return await self._handle_debate(query, task_ctx, publish)
            
        # ── Deep Research ────────────────────────────────────────────────
        if intent == "research":
            return await self._handle_research(query, task_ctx, publish)

        # ── Multi-Agent Pipeline (tool / coding tasks) ───────────────────
        if intent == "tool":
            tool_type = route.metadata.get("tool")
            if tool_type == "search":
                from backend.agents.specialized.web_agent import WebAgent
                agent = WebAgent(provider=self._provider, model=self._model)
                publish({
                    "type": "agent", "agent": "web_agent", "role": "system",
                    "status": "running", "content": "🔎 Searching the web...",
                })
                result = await agent.search(query)
                publish({"type": "final", "content": result})
                return result
            elif tool_type == "file":
                from backend.agents.specialized.file_agent import FileAgent
                agent = FileAgent(provider=self._provider, model=self._model)
                publish({
                    "type": "agent", "agent": "file_agent", "role": "system",
                    "status": "running", "content": "📄 Reading local files...",
                })
                result = await agent.read_and_answer(query)
                publish({"type": "final", "content": result})
                return result

            return await self._handle_pipeline(query, task_ctx, publish)

        # ── Default: full orchestrator chat ──────────
        return await self._handle_chat(query, task_ctx, publish, convo_id)

    async def _handle_builder(
        self, query: str, task_ctx: TaskContext,
        publish: Callable,
    ) -> str:
        from backend.builder.preference_parser import finalize_preferences
        from backend.builder import build_website
        from backend.core.context_manager import get_agent_context, save_agent_context

        pco_context = get_agent_context(self._user_id, self._bot_id)

        # ── Handle JSON form submission from the inline widget ───────────────
        # When the form widget submits, it sends: "Build this website: {json}"
        if query.strip().startswith("Build this website:"):
            try:
                import json as _json
                json_str = query[len("Build this website:"):].strip()
                form_data = _json.loads(json_str)
                # Map form fields directly to builder prefs — always fresh, never reused
                build_prefs = {
                    "name":     form_data.get("name", "Untitled"),
                    "type":     form_data.get("type", "landing"),
                    "design":   form_data.get("design", "modern"),
                    "features": form_data.get("features", []),
                    "backend":  form_data.get("database", {}).get("enabled", False),
                    "database": form_data.get("database", {}).get("type", "sqlite") if form_data.get("database", {}).get("enabled") else None,
                    "purpose":  form_data.get("purpose", ""),
                    "products": form_data.get("products", []),
                    "contact":  form_data.get("contact", {}),
                    "socials":  form_data.get("socials", []),
                    "footer":   form_data.get("footer", ""),
                    "audience": form_data.get("audience", []),
                    "pages":    form_data.get("pages", ["home", "contact"]),
                }
                build_prefs = finalize_preferences(build_prefs)
                # Store only for the duration of this build, then clear
                pco_context["builder_preferences"] = build_prefs
                save_agent_context(self._user_id, self._bot_id, pco_context)
                logger.info("[Builder] Form submission parsed — launching fresh build.")
                goto_build = True
            except Exception as e:
                logger.warning(f"[Builder] Failed to parse form JSON: {e}")
                goto_build = False
        else:
            # ── Any other builder intent: ALWAYS show the form fresh ──────────
            # Never reuse stored preferences. Clear them and ask again.
            pco_context["builder_preferences"] = {}
            save_agent_context(self._user_id, self._bot_id, pco_context)
            publish({"type": "builder_form", "content": "open_form"})
            reply = "Let me open the website builder for you 🚀"
            publish({"type": "final", "content": reply})
            return reply

        # ── goto_build is True here — form JSON was parsed and finalized ──────
        if not goto_build:
            # JSON parse failed — show the form again
            publish({"type": "builder_form", "content": "open_form"})
            reply = "Something went wrong parsing your form. Let me try again 🔄"
            publish({"type": "final", "content": reply})
            return reply

        # build_prefs is already set and finalized from the form submission block.
        # Clear stored prefs after execution so next request always shows fresh form.
        pco_context["builder_preferences"] = {}
        save_agent_context(self._user_id, self._bot_id, pco_context)

        # ── Execute the build ─────────────────────────────────────────────────
        project_type = build_prefs.get("type", "website")

        # Emit first progress step so UI shows the bar immediately
        publish({
            "type": "builder_step",
            "step": "init",
            "message": f"⚙️ Starting {project_type} build...",
            "progress": 5
        })

        def _build_publish(event):
            publish(event)

        # Emit builder_started so the UI can open the BuilderPanel
        publish({
            "type": "builder_started",
            "task_id": task_ctx.task_id
        })

        async def _background_build_job():
            try:
                build_res = await build_website(build_prefs, publish_event=_build_publish)

                if build_res.error:
                    publish({"type": "builder_error", "message": f"Builder failed: {build_res.error}"})
                    publish({"type": "final", "content": f"❌ Builder failed: {build_res.error}"})
                    return

                publish({
                    "type": "builder_done",
                    "url": f"http://localhost:3000/preview/{build_res.session_id}",
                    "session_id": build_res.session_id,
                    "message": "🚀 Your site is ready!"
                })
                publish({"type": "final", "content": "✅ Build complete! Your website is ready."})

            except Exception as e:
                logger.error(f"[Builder] Background build crashed: {e}", exc_info=True)
                publish({"type": "builder_error", "message": f"Builder crashed: {str(e)}"})
                publish({"type": "final", "content": f"❌ Builder crashed: {str(e)}"})

        # Offload to background — TRACK task, register done_callback for auto-cleanup
        job_id = task_ctx.task_id
        JOB_STATUS[job_id] = "running"

        async def _tracked_build():
            try:
                await _background_build_job()
                JOB_STATUS[job_id] = "done"
            except Exception as e:
                JOB_STATUS[job_id] = "error"
                logger.error("[Builder] Tracked build failed: %s", e)

        task = asyncio.create_task(_tracked_build())
        RUNNING_TASKS[job_id] = task
        # Auto-cleanup when task finishes — prevents RAM leak
        task.add_done_callback(lambda _: _cleanup_job(job_id))

        return "Build started in background."

    async def _handle_update(
        self, query: str, session_id: str,
        task_ctx: TaskContext, publish: Callable,
    ) -> str:
        from backend.builder.updater import apply_update

        publish({
            "type": "agent", "agent": "builder", "role": "system",
            "status": "running", "content": "🔄 Analyzing your update request...",
        })

        async def _do_update():
            return await apply_update(session_id, query, publish_event=publish)

        res = await with_retry(_do_update, task_ctx, publish, max_retries=1)

        if "error" in res:
            publish({"type": "error", "content": f"Update failed: {res['error']}"})
            return f"Update failed: {res['error']}"

        v = res["version"]
        reply = (
            f"✅ **Update Complete!** (Version {v})\n\n"
            f"I've applied your changes to the project.\n"
            f"You can preview it now or download the latest source."
        )
        publish({"type": "final", "content": reply})
        return reply

    async def _handle_continue(
        self, query: str, task_ctx: TaskContext, publish: Callable,
    ) -> str:
        from backend.core.context_manager import get_agent_context

        pco = get_agent_context(self._user_id, self._bot_id)
        last_build = pco.get("last_build", {})

        if not last_build:
            reply = "I couldn't find a previous project to continue. Would you like to start a new one?\n\n[🔘 Start new project](action:make website)"
        else:
            name = f"{last_build.get('project_type', 'Website').title()} v{last_build.get('version', 1)}"
            reply = (
                f"I found your last project: **{name}** 👍\n\n"
                f"What would you like to change?\n\n"
                f"[🔘 Make it dark mode](action:make it dark mode) [🔘 Add login page](action:add a login page) [🔘 Just build it](action:use this)"
            )

        publish({"type": "final", "content": reply})
        task_ctx.transition(TaskState.COMPLETED)
        return reply

    async def _handle_autonomous(
        self, query: str, task_ctx: TaskContext,
        publish: Callable, convo_id: Optional[str] = None,
    ) -> str:
        """Delegate to the autonomous controller (AutoGPT-style loop)."""
        from backend.agents.autonomous.autonomous_manager import AutonomousManager
        from backend.agents.autonomous.event_adapter import to_chat_event
        from backend.llm.universal_provider import universal_provider

        publish({
            "type": "agent", "agent": "orchestrator", "role": "system",
            "status": "running",
            "content": "🤖 Autonomous Mode detected. Launching Task Engine...",
        })

        manager = AutonomousManager(provider=universal_provider)
        final_eval = ""

        async for event in manager.stream(None, None, query):
            publish(to_chat_event(event))
            if event.get("type") == "final":
                final_eval = str(event.get("data", {}).get("final_evaluation", ""))

        publish({
            "type": "agent", "agent": "orchestrator", "role": "system",
            "status": "done", "content": "✅ Engine finished.",
        })

        return f"**Autonomous Task Cycle Completed:**\n{final_eval}"

    async def _handle_news(
        self, query: str, task_ctx: TaskContext, publish: Callable,
    ) -> str:
        """
        News MUST come from real sources only.
        Uses arun() (async) to avoid blocking the event loop.
        NEVER falls back to LLM. If tool fails, returns a clear error.
        On zero results: auto-expands query once before giving up.
        """
        publish({
            "type": "agent", "agent": "news_analyst", "role": "system",
            "status": "running",
            "content": "📰 Fetching live news from real sources...",
        })
        try:
            from backend.tools.news import NewsAnalystTool
            tool = NewsAnalystTool()
            
            import asyncio
            result = None
            
            # ✅ Add loop with timeout fallsafes (45s to cover multi-source fetch)
            for _ in range(2):
                try:
                    result = await asyncio.wait_for(tool.arun(query), timeout=45)
                    if result:
                        break
                except asyncio.TimeoutError:
                    publish({
                        "type": "step",
                        "content": "⏳ Search took too long. Retrying with simplified query...",
                        "agent": "news_analyst"
                    })
                    continue
            
            if not result:
                return "⚠️ **News request timed out.** News sources are currently slow or unavailable. Please try again in a moment."

            # If zero results, process smart query expansions
            _no_result_phrases = (
                "no live news found",
                "no unique news",
                "no recent news",
                "insufficient unique",
            )
            if not result or any(p in result.lower() for p in _no_result_phrases):
                # Detect Zero Result Loop - simplify query
                import re
                fluff = ["latest", "updates", "perspective", "detailed", "in", "about", "give me", "news"]
                simplified_query = query.lower()
                for f in fluff:
                    simplified_query = simplified_query.replace(f, "")
                simplified_query = re.sub(r'\s+', ' ', simplified_query).strip()
                if not simplified_query:
                    simplified_query = "news headlines"

                EXPANSIONS = [
                    f"{simplified_query}",
                    f"{simplified_query} breaking",
                    f"{simplified_query} global",
                    f"{simplified_query} headlines"
                ]

                # Try the smart expansions
                for exp in EXPANSIONS:
                    if exp == query: continue # Skip if identical
                    publish({
                        "type": "step",
                        "content": f"🔄 Simplifying search: `{exp}`...",
                        "agent": "news_analyst"
                    })
                    try:
                        result = await asyncio.wait_for(tool.arun(exp), timeout=35)
                        if result and not any(p in result.lower() for p in _no_result_phrases):
                            break
                    except asyncio.TimeoutError:
                        continue

            if not result or len(result.strip()) < 20:
                raise ValueError("Empty news result after retry")

            # Attach intent debug metadata
            publish({
                "type": "intent_debug",
                "intent": "news",
                "confidence": 0.97,
                "source": "priority_router",
            })
            publish({"type": "final", "content": result})
            return result

        except Exception as e:
            logger.error("[NewsHandler] Tool failed: %s", e, exc_info=True)
            # ❌ NEVER fallback to LLM for news
            error_msg = (
                "⚠️ **Live news temporarily unavailable.**\n\n"
                "The news service could not fetch real-time data right now. "
                "Please try again in a moment or check a news site directly.\n\n"
                f"_Technical: {type(e).__name__}_"
            )
            publish({"type": "final", "content": error_msg})
            return error_msg

    async def _handle_pipeline(
        self, query: str, task_ctx: TaskContext, publish: Callable,
    ) -> str:
        """5-stage Multi-Agent Pipeline: Planner → Coder → Tester → Fixer → Reviewer."""
        import asyncio
        import os
        from backend.agents.pipeline import MultiAgentPipeline

        # 5 agents × ~30s LLM call each = 150s minimum. Give 5 minutes headroom.
        PIPELINE_TIMEOUT = int(os.environ.get("PIPELINE_TIMEOUT_SECONDS", 300))

        publish({
            "type": "agent", "agent": "pipeline", "role": "system",
            "status": "running",
            "content": f"🚀 Launching Multi-Agent Pipeline (Timeout: {PIPELINE_TIMEOUT}s)...",
        })

        pipeline = MultiAgentPipeline(provider=self._provider, model=self._model)

        async def _do_pipeline():
            return await pipeline.run(task=query, publish=publish)

        try:
            result = await asyncio.wait_for(
                with_retry(_do_pipeline, task_ctx, publish),
                timeout=PIPELINE_TIMEOUT
            )
            publish({"type": "final", "content": result})
            return result
        except asyncio.TimeoutError:
            error_msg = f"Pipeline timeout exceeded ({PIPELINE_TIMEOUT}s)"
            publish({"type": "error", "content": error_msg})
            task_ctx.error = error_msg
            if task_ctx.state != TaskState.FAILED:
                task_ctx.transition(TaskState.FAILED)
            return error_msg

    async def _handle_chat(
        self, query: str, task_ctx: TaskContext,
        publish: Callable, convo_id: Optional[str] = None,
    ) -> str:
        """Fast Orchestrator. Completely bypasses recursive agents."""
        from backend.agents.fast_orchestrator import FastOrchestrator
        from backend.core.context_manager import get_agent_context, build_system_prompt, update_context, save_agent_context
        from backend.core.background_worker import bg_worker
        from backend.llm.universal_provider import UniversalProvider

        pco_context = get_agent_context(user_id=self._user_id, bot_id=self._bot_id)
        system_prompt = build_system_prompt(pco_context)
        
        orchestrator = FastOrchestrator(provider=self._provider, model=self._model)
        
        final_content = ""
        
        # Process FastOrchestrator's stream natively
        async for event in orchestrator.stream_handle(query, context=system_prompt):
            if event["event"] == "status":
                # Maps cleanly to UX streaming 
                publish({
                    "type": "agent", "agent": "orchestrator", "role": "system",
                    "status": "running", "content": event["message"]
                })
            elif event["event"] == "final":
                final_payload = event["data"]
                final_content = final_payload["content"]
                publish({"type": "final", "content": final_content, "structured": final_payload.get("structured", {})})

        # Background the PCO Update using bounding task queue so it never blocks the event loop
        async def _background_pco_update():
            try:
                llm = UniversalProvider(provider=self._provider, model=self._model)
                updated_pco = await update_context(llm, pco_context, f"User: {query}\nAssistant: {final_content}")
                save_agent_context(user_id=self._user_id, bot_id=self._bot_id, context=updated_pco)
            except Exception as exc:
                logger.warning("[Dispatcher] Background PCO update failed: %s", exc)
                
        await bg_worker.submit(_background_pco_update())

        return final_content

    async def _handle_debate(self, query: str, task_ctx: TaskContext, publish: Callable) -> str:
        """Handle debate queries by routing to the DebateAgent."""
        from backend.agents.debate_agent import DebateAgent
        from backend.llm.universal_provider import UniversalProvider
        llm = UniversalProvider(provider=self._provider, model=self._model)
        agent = DebateAgent(llm)
        
        result = await agent.debate(query, publish=publish)
        publish({"type": "final", "content": result})
        return result
        
    async def _handle_research(self, query: str, task_ctx: TaskContext, publish: Callable) -> str:
        """Handle research queries by routing to the ResearchAgent."""
        from backend.agents.research_agent import ResearchAgent
        from backend.llm.universal_provider import UniversalProvider
        llm = UniversalProvider(provider=self._provider, model=self._model)
        agent = ResearchAgent(llm)
        
        publish({
            "type": "agent", "agent": "research", "role": "system",
            "status": "running", "content": "🔎 Engaging Deep Research..."
        })
        
        result = await agent.research(query, depth="deep")
        publish({"type": "final", "content": result})
        return result

