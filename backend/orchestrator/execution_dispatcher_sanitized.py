"""
backend/orchestrator/execution_dispatcher.py

Central dispatch layer: takes a RouteDecision and delegates
to the correct agent/subsystem.  This is the missing link between
routing and execution — prevents logic from leaking into chat_worker.py.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from backend.orchestrator.intent_router import RouteDecision
from backend.orchestrator.task_state import TaskContext, TaskState
from backend.orchestrator.retry import with_retry, get_max_retries
from backend.orchestrator.observability import TaskLogger

logger = logging.getLogger(__name__)


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

        # ── Default: full orchestrator chat ──────────�    async def _handle_builder(
        self, query: str, task_ctx: TaskContext,
        publish: Callable,
    ) -> str:
        from backend.builder.preference_parser import (
            smart_parse_preferences, check_missing_preferences,
            get_rejection_response, build_prefs_summary
        )
        from backend.builder import build_website
        from backend.core.context_manager import get_agent_context, save_agent_context

        pco_context = get_agent_context(self._user_id, self._bot_id)
        prefs = pco_context.get("builder_preferences", {})

        parsed_now = await smart_parse_preferences(query)

        # ── Handle product type update ("no product type mobiles") ──────────
        if parsed_now.get("_product_update"):
            updated_prefs = prefs.copy()
            updated_prefs["product_type"] = parsed_now.get("product_type", "")
            if parsed_now.get("type"):
                updated_prefs["type"] = parsed_now["type"]
            pco_context["builder_preferences"] = updated_prefs
            save_agent_context(self._user_id, self._bot_id, pco_context)
            prefs = updated_prefs

            summary = build_prefs_summary(prefs)
            reply = (
                f"Got it! Updated your plan \ud83d\udc4d\n\n"
                f"{summary}\n\n"
                f"Ready to build?\n\n"
                f"[\ud83d\udd18 Build it now](action:use this)  [\ud83d\udd18 Change something](action:no)"
            )
            publish({"type": "builder_ui", "content": reply})
            publish({"type": "final", "content": reply})
            return reply

        # Check if user directly confirmed pending draft
        if parsed_now.get("_confirmation"):
            if prefs:
                build_prefs = prefs
            else:
                publish({"type": "builder_ui", "content": "I lost your draft preferences. What kind of project do you want?\n\n[\ud83d\udd18 Start from scratch](action:make website)"})
                publish({"type": "final", "content": "I lost your draft preferences. What kind of project do you want?\n\n[\ud83d\udd18 Start from scratch](action:make website)"})
                return ""

        # Check if user explicitly rejected / wants to edit
        elif parsed_now.get("_rejection"):
            rejection_msg = get_rejection_response(prefs)
            publish({"type": "builder_ui", "content": rejection_msg})
            publish({"type": "final", "content": rejection_msg})
            return rejection_msg

        elif parsed_now.get("_ambiguous"):
            ambig = "I didn't fully get that \ud83d\udc4d\n\n[\ud83d\udd18 Use current plan](action:use this) [\ud83d\udd18 Change something](action:no)"
            publish({"type": "builder_ui", "content": ambig})
            publish({"type": "final", "content": ambig})
            return ambig

        else:
            # Merge with existing prefs — new non-None values win
            build_prefs = prefs.copy()
            for k, v in parsed_now.items():
                if v is not None:
                    build_prefs[k] = v

        # Check for missing required fields
        clarification_msg = check_missing_preferences(build_prefs)

        # Persist merged draft even if incomplete
        pco_context["builder_preferences"] = build_prefs
        save_agent_context(self._user_id, self._bot_id, pco_context)

        if clarification_msg:
            publish({"type": "builder_ui", "content": clarification_msg})
            publish({"type": "final", "content": clarification_msg})
            return clarification_msg

        pt_label = build_prefs.get("product_type", "")
        publish({
            "type": "agent", "agent": "builder", "role": "system",
            "status": "running",
            "content": (
                f"\ud83c\udfd7\ufe0f Commencing build for {build_prefs.get('type')} project"
                f"{(' \u2014 ' + pt_label) if pt_label else ''}..."
            ),
        })

        async def _do_build():
            return build_website(build_prefs, publish_event=publish)

        build_res = await with_retry(
            _do_build, task_ctx, publish, max_retries=task_ctx.max_retries,
        )

        if build_res.error:
            publish({"type": "error", "content": f"Builder failed: {build_res.error}"})
            return f"Builder failed: {build_res.error}"

        pt_note = f"\n\ud83d\udecb\ufe0f **Selling:** {pt_label}" if pt_label else ""
        reply = (
            f"\u2705 **Build Complete!**\n\n"
            f"Project Location: `{build_res.output_path}`{pt_note}\n"
            f"I've initialized **Version 1** of your project."
        )
        publish({"type": "final", "content": reply})
        return replyuild_website(build_prefs, publish_event=publish)

        build_res = await with_retry(
            _do_build, task_ctx, publish, max_retries=task_ctx.max_retries,
        )

        if build_res.error:
            publish({"type": "error", "content": f"Builder failed: {build_res.error}"})
            return f"Builder failed: {build_res.error}"

        reply = (
            f"✅ **Build Complete!**\n\n"
            f"Project Location: `{build_res.output_path}`\n"
            f"I've initialized **Version 1** of your project."
        )
        publish({"type": "final", "content": reply})
        return reply

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

    async def _handle_pipeline(
        self, query: str, task_ctx: TaskContext, publish: Callable,
    ) -> str:
        """5-stage Multi-Agent Pipeline: Planner → Coder → Tester → Fixer → Reviewer."""
        import asyncio
        from backend.agents.pipeline import MultiAgentPipeline

        PIPELINE_TIMEOUT = 45  # seconds

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
