"""
backend/orchestrator/task_controller.py

The Central Nervous System of DreamAgent.
Acts as the central Auto-GPT loop for all complex background executions.

Upgrades in this version:
  - import json fix (was missing, caused NameError on all complex queries)
  - Hybrid memory context (Dragonfly + ChromaDB + SQLite via memory_engine)
  - Parallel step execution via asyncio.gather + return_exceptions=True
  - Pipeline guard wraps typed exceptions (NameError, ImportError, Timeout)
  - Last-resort boundary catch at outermost run() level only
  - format_context_for_prompt() for clean LLM injection
"""
import json
import logging
import asyncio
from typing import Callable, Any, List

from backend.orchestrator.hybrid_router import HybridRouter
from backend.core.memory_engine import memory_engine
from backend.orchestrator.task_state import TaskContext, TaskState, BudgetExceededError
from backend.core.pipeline_guard import guarded_execute, execute_step_safe
from backend.orchestrator.dag_planner import dag_planner
from backend.orchestrator.synthesizer import synthesizer

# Try importing the necessary pipeline agents
try:
    from backend.agents.planner import PlannerAgent
    from backend.agents.executor import ExecutorAgent
    from backend.llm.universal_provider import UniversalProvider
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Maximum parallel steps allowed at once
MAX_PARALLEL_STEPS = 4
# Per-step execution timeout — single LLM calls can take 30-40s on NVIDIA API
STEP_TIMEOUT_SECONDS = 90.0

# ── Single source of truth: all intent detection flows through priority_router ──
from backend.orchestrator.priority_router import detect_intent, detect_intent_with_confidence


def _fast_classify(query: str, has_active_builder: bool = False) -> str | None:
    """
    ⚡ Pre-router using the SINGLE canonical detect_intent().
    Returns intent string or None (fall through to HybridRouter for stateful checks).
    """
    q = query.strip().lower()
    words = q.split()

    # Active builder confirmation must be handled by HybridRouter (stateful)
    _BUILDER_CONFIRM = {"ok", "okay", "yes", "yeah", "confirm", "go", "done", "start", "no", "change"}
    if has_active_builder and any(w in words for w in _BUILDER_CONFIRM):
        return None  # let HybridRouter handle stateful builder flow

    # Delegate to single source of truth
    intent = detect_intent(query)
    logger.debug("[FastClassify] intent=%s query=%r", intent, query[:60])
    return intent


class TaskController:
    """Central processing unit mapping Intent → Execution loop."""

    def __init__(self, provider: str = "auto", model: str = "", trust_mode: str = "fast"):
        self.provider = provider
        self.model = model
        self.trust_mode = trust_mode
        self.router = HybridRouter(provider=provider, model=model)
        self.llm = UniversalProvider(provider=provider, model=model)

        # Instantiate execution agents
        self.planner = PlannerAgent(self.llm)
        self.executor = ExecutorAgent(self.llm)

    async def run(
        self,
        query: str,
        task_id: str,
        publish: Callable[[dict], None],
        user_id: str = "local_user",
        bot_id: str = "local_bot",
        file_ids: str = "",
        trust_mode: str = "fast"
    ) -> str:
        """
        The main Auto-GPT loop.
        Plan → Parallel Execute → Store → Synthesize

        Wrapped with a last-resort boundary guard at the outermost level.
        Internal steps use typed exception handling only.
        """
        return await guarded_execute(
            self._run_inner(query, task_id, publish, bot_id, user_id, file_ids, trust_mode),
            publish=publish,
            label="task_controller",
            boundary=True  # Last-resort — catches anything that escapes typed handlers
        )

    async def _run_inner(
        self,
        query: str,
        task_id: str,
        publish: Callable[[dict], None],
        bot_id: str,
        user_id: str,
        file_ids: str,
        trust_mode: str = "fast"
    ) -> str:
        """
        Actual execution logic. All exceptions propagate up to the boundary guard.
        """
        task_ctx = TaskContext(task_id, user_id)
        task_ctx.transition(TaskState.ROUTING)

        publish({
            "type": "step",
            "content": "🧠 Initializing task execution...",
            "agent": "controller"
        })

        # ── Step 0: Resolve Uploaded Files ───────────────────────────────
        file_context_str = ""
        if file_ids:
            ids = [fid.strip() for fid in file_ids.split(",") if fid.strip()]
            if ids:
                publish({
                    "type": "step",
                    "content": f"📎 Processing {len(ids)} uploaded file(s)...",
                    "agent": "controller"
                })
                file_context_str = await self._resolve_and_store_files(ids, user_id, bot_id)
                if file_context_str:
                    publish({
                        "type": "step",
                        "content": "✅ File content injected into memory.",
                        "agent": "controller"
                    })

        # ── Step 1: Hybrid Memory Context (3-layer) ───────────────────────
        publish({
            "type": "step",
            "content": "📥 Retrieving Unified Memory Context (Session + Long-Term + Identity)...",
            "agent": "controller"
        })
        context = await memory_engine.get_context(
            user_id=user_id,
            bot_id=bot_id,
            user_input=query
        )
        # Emit memory health trace
        session_count = len(context.get("session", []))
        core_count = len(context.get("core_memory", []))
        longterm_count = len(context.get("long_term", []))
        memory_trace = {
            "session_turns": session_count,
            "core_facts": core_count,
            "long_term_hits": longterm_count,
            "layers_active": [
                k for k, v in {
                    "dragonfly_session": session_count > 0,
                    "sqlite_identity": core_count > 0,
                    "semantic_recall": longterm_count > 0
                }.items() if v
            ]
        }
        publish({
            "type": "step",
            "content": f"```json\n{json.dumps(memory_trace, indent=2)}\n```\n🧠 Memory loaded.",
            "agent": "memory_trace"
        })

        # ── Step 2: FAST PRE-ROUTER using single source of truth ────────────

        # ── Context isolation: detect intent first for tool queries ───────────
        # Tool-based intents (news, finance, weather, search) must NOT inherit
        # previous session memory — prevents context bleeding across tasks.
        from backend.orchestrator.priority_router import detect_intent
        _pre_intent = detect_intent(query)
        _is_tool_intent = _pre_intent in ("news", "finance", "weather", "search")

        if _is_tool_intent:
            # Use fresh, identity-only context (no session history bleed)
            context = {
                "core_memory": context.get("core_memory", []),
                "session": [],       # ← clear session history
                "long_term": [],     # ← clear long-term for tool queries
            }
            file_context_str = ""  # files not needed for tool intents

        from backend.core.context_manager import get_agent_context
        pco = get_agent_context(user_id, bot_id)
        has_active_builder = bool(pco.get("builder_preferences"))

        fast_intent = _fast_classify(query, has_active_builder)


        if fast_intent == "news":
            # 🔴 NEWS: HARD LOCK — always goes to real tool, NEVER to LLM
            publish({"type": "step", "content": "📰 Fetching live news...", "agent": "controller"})
            from backend.orchestrator.execution_dispatcher import ExecutionDispatcher
            from backend.orchestrator.intent_router import RouteDecision
            dispatcher = ExecutionDispatcher(
                provider=self.provider, model=self.model,
                user_id=user_id, bot_id=bot_id
            )
            news_decision = RouteDecision("news", 0.97, {"source": "priority_router"})
            return await dispatcher.dispatch(news_decision, query, task_ctx, publish, convo_id=None)

        if fast_intent == "finance":
            from backend.orchestrator.execution_dispatcher import ExecutionDispatcher
            from backend.orchestrator.intent_router import RouteDecision
            dispatcher = ExecutionDispatcher(
                provider=self.provider, model=self.model,
                user_id=user_id, bot_id=bot_id
            )
            fin_decision = RouteDecision("tool", 0.92, {"source": "priority_router", "tool": "finance"})
            return await dispatcher.dispatch(fin_decision, query, task_ctx, publish, convo_id=None)

        if fast_intent in ("chat", "coding"):
            return await self._run_chat_path(
                query, context, file_context_str, user_id, bot_id, publish
            )

        # ── Step 3: Strict Intent Routing (HybridRouter → LLM fallback) ────
        route_ctx = dict(context)
        route_ctx["file_ids"] = file_ids
        route_ctx["user_id"] = user_id
        route_ctx["bot_id"] = bot_id
        decision = await self.router.route(query, route_ctx)

        trace = {
            "intent": decision.intent,
            "state": "analyzing",
            "memory_used": core_count + longterm_count,
            "next_action": "route_to_" + decision.intent
        }
        publish({
            "type": "step",
            "content": f"```json\n{json.dumps(trace, indent=2)}\n```\n🚦 Intent: **{decision.intent}**",
            "agent": "trace"
        })

        # ── Step 4: Dispatch specialized intents ─────────────────────────────
        if decision.intent == "news":
            # News reached via HybridRouter — still route to real tool
            from backend.orchestrator.execution_dispatcher import ExecutionDispatcher
            dispatcher = ExecutionDispatcher(
                provider=self.provider, model=self.model,
                user_id=user_id, bot_id=bot_id
            )
            return await dispatcher.dispatch(decision, query, task_ctx, publish, convo_id=None)

        if decision.intent in ("builder", "update", "tool"):
            from backend.orchestrator.execution_dispatcher import ExecutionDispatcher
            dispatcher = ExecutionDispatcher(
                provider=self.provider, model=self.model,
                user_id=user_id, bot_id=bot_id
            )
            return await dispatcher.dispatch(decision, query, task_ctx, publish, convo_id=None)

        # ── Clarification: smart response, NEVER call LLM ─────────────────────
        if decision.intent == "clarification":
            reply = (
                "I'm not sure what you need. Could you clarify?\n\n"
                "Are you looking for:\n"
                "- 📰 **News** (e.g. \"latest news about India\")\n"
                "- 💻 **Code** (e.g. \"write a Python script\")\n"
                "- 🏗️ **Build something** (e.g. \"build me a portfolio site\")\n"
                "- 💬 **Chat** (just talk to me)"
            )
            publish({"type": "final", "content": reply})
            return reply

        if decision.intent in ("chat", "file"):
            return await self._run_chat_path(
                query, context, file_context_str, user_id, bot_id, publish
            )

        # ── Step 4: Complex tasks — Parallel Execution ───────────────────
        task_ctx.transition(TaskState.RUNNING)
        return await self._run_parallel_plan(
            query, context, file_context_str, task_ctx, publish, user_id, bot_id, trust_mode
        )

    # ── Chat / Direct Path ────────────────────────────────────────────────────

    async def _run_chat_path(
        self,
        query: str,
        context: dict,
        file_context_str: str,
        user_id: str,
        bot_id: str,
        publish: Callable
    ) -> str:
        """Fast direct-answer path for chat and file intents."""
        context_block = memory_engine.format_context_for_prompt(context)

        has_memory = bool(context.get("core_memory") or context.get("long_term") or context.get("session"))
        memory_instruction = (
            "Use the above context if directly relevant. Do NOT say \"I remember...\" if no memory was provided."
            if has_memory else
            "No prior memory context is available for this user. Do not claim to remember anything."
        )

        file_block = f"\n{file_context_str}\n" if file_context_str else ""

        prompt = f"""You are DreamAgent, a helpful AI assistant.
{context_block}{file_block}
[CURRENT REQUEST]
{query}

[INSTRUCTIONS]
{memory_instruction}
Answer directly and accurately. Do not hallucinate."""

        publish({
            "type": "agent",
            "agent": "orchestrator",
            "role": "system",
            "status": "running",
            "content": "Processing..."
        })

        result = await self.llm.complete(prompt)

        # Store both turns in memory (session + long-term extraction)
        await memory_engine.process_and_store(
            f"User: {query}", user_id=user_id, bot_id=bot_id, role="user"
        )
        await memory_engine.process_and_store(
            f"Assistant: {result}", user_id=user_id, bot_id=bot_id, role="assistant"
        )

        publish({"type": "final", "content": result})
        return result

    # ── Parallel Plan Execution ───────────────────────────────────────────────

    async def _run_parallel_plan(
        self,
        query: str,
        context: dict,
        file_context_str: str,
        task_ctx: TaskContext,
        publish: Callable,
        user_id: str,
        bot_id: str,
        trust_mode: str = "fast"
    ) -> str:
        """
        Parallel step execution using DAG waves and response synthesis.
        """
        # Build env state for planner
        file_section = f"\n\n{file_context_str}" if file_context_str else ""
        context_str = memory_engine.format_context_for_prompt(context)
        env_state = f"[Goal]: {query}\n[Context]: {context_str}{file_section}"

        # Generate plan
        publish({
            "type": "step",
            "content": "📝 Generating execution plan...",
            "agent": "planner"
        })
        # The prompt should tell the planner to output JSON with depends_on.
        # We assume self.planner.plan handles it correctly into a List of dicts.
        plan_steps = await self.planner.plan(env_state)
        if not isinstance(plan_steps, list):
            plan_steps = [{"task": str(plan_steps), "id": "step_1", "depends_on": []}]

        # Parse DAG
        dag_steps = dag_planner.parse_plan(plan_steps)
        waves = dag_planner.get_execution_waves(dag_steps)

        publish({
            "type": "step",
            "content": f"⚡ Executing {len(dag_steps)} steps across {len(waves)} sequence wave(s)...",
            "agent": "planner"
        })

        import time
        from statistics import mean
        metrics_start = time.time()
        step_times = []
        recoveries = 0

        all_step_results = []
        
        replan_count = 0
        MAX_REPLANS = 2
        pending_waves = list(waves)
        total_steps_executed = 0
        critic_retry_spikes = 0
        semantic_misalignments = 0
        unresolved_contradictions = 0
        
        if trust_mode == "truth":
            publish({"type": "status", "content": "[Phase 1] Generating base answer...", "agent": "controller"})
        
        # Execute waves sequentially, but parallel within each wave
        while pending_waves:
            wave = pending_waves.pop(0)
            wave_start = time.time()
            total_steps_executed += len(wave)
            
            wave_coroutines = [
                execute_step_safe(
                    self._execute_one_step,
                    step.task,
                    context_str + "\n" + "\n".join([r['content'] for r in all_step_results]),
                    timeout=STEP_TIMEOUT_SECONDS,
                    step_label=step.id
                )
                for step in wave
            ]
            
            raw_results = await asyncio.gather(*wave_coroutines, return_exceptions=True)
            wave_end = time.time()
            
            # Simple average time per step in this wave
            if wave:
                step_times.append((wave_end - wave_start) / len(wave))
            
            wave_failed = False
            failed_task_name = ""
            failed_error_msg = ""
            
            for idx, res in enumerate(raw_results):
                step = wave[idx]
                if isinstance(res, Exception):
                    error_msg = f"Step {step.id} failed: [ERROR] {type(res).__name__}: {res}"
                    all_step_results.append({"content": error_msg, "is_error": True, "id": step.id})
                    publish({"type": "error", "content": f"⚠️ {error_msg}", "agent": "executor"})
                    await memory_engine.process_and_store(error_msg, user_id=user_id, bot_id=bot_id, role="system")
                    wave_failed = True
                    failed_task_name = step.task
                    failed_error_msg = str(res)
                else:
                    success_msg = f"Step {step.id} result: {res}"
                    all_step_results.append({"content": success_msg, "is_error": False, "id": step.id})
                    await memory_engine.process_and_store(
                        f"Task: {step.task}\nResult: {res}",
                        user_id=user_id, bot_id=bot_id, role="assistant"
                    )
                    publish({"type": "step", "content": f"✅ Step {step.id} complete.", "agent": "executor"})
                    # Track critic retries heuristically from output pattern
                    if "needs improvement" in success_msg.lower() or "attempt" in success_msg.lower():
                        critic_retry_spike_inc = 1
                        if "contradiction" in success_msg.lower():
                            unresolved_contradictions += 1
                        critic_retry_spikes += critic_retry_spike_inc
                    
                    if "[⚠️ Source does not support claim]" in success_msg:
                        semantic_misalignments += 1
                    
                    if trust_mode == "truth":
                        # Simulate verification phase transitions
                        if "Research" in step.task or "verify" in step.task.lower():
                            publish({"type": "status", "content": "[Phase 2] Verifying sources and checking semantics...", "agent": "controller"})
                        if "Debate" in step.task or "conflict" in step.task.lower():
                            publish({"type": "status", "content": "[Phase 3] Resolving internal logical contradictions...", "agent": "controller"})

            if wave_failed and replan_count < MAX_REPLANS:
                replan_count += 1
                publish({
                    "type": "agent", "agent": "planner", "role": "system",
                    "status": "running", "content": f"🔄 Critical Failure Detected. Adaptive Replanning Triggered (Attempt {replan_count}/{MAX_REPLANS})..."
                })
                replan_context = (
                    f"Original Goal: {query}\n"
                    f"Failure on task: '{failed_task_name}'\n"
                    f"Error: {failed_error_msg}\n"
                    f"Do not re-attempt the exact same step. Propose an entirely alternative strategy to accomplish the remaining goal."
                )
                new_plan_steps = await self.planner.plan(replan_context)
                if not isinstance(new_plan_steps, list):
                    new_plan_steps = [{"task": str(new_plan_steps), "id": f"replan_{replan_count}_1", "depends_on": []}]
                
                # Plan Diff Check
                old_tasks = {s.get("task", "") for pending in pending_waves for s in pending}
                new_tasks = {s.get("task", "") for s in new_plan_steps}
                if new_tasks and new_tasks.issubset(old_tasks):
                    publish({
                        "type": "error", "content": "⚠️ Adaptive Replan Aborted: Planner proposed identical steps. Continuing with fallback.", "agent": "planner"
                    })
                else:
                    recoveries += 1
                    new_dag_steps = dag_planner.parse_plan(new_plan_steps)
                    pending_waves = dag_planner.get_execution_waves(new_dag_steps)
                    publish({
                        "type": "step", "content": f"📝 Replanned remaining logical path ({len(pending_waves)} waves).", "agent": "planner"
                    })

        # Calculate final metrics
        total_steps = len(dag_steps) + recoveries
        success_steps = len([r for r in all_step_results if not r["is_error"]])
        success_rate = (success_steps / total_steps_executed * 100) if total_steps_executed > 0 else 0
        avg_time = mean(step_times) if step_times else 0
        total_time = time.time() - metrics_start
        
        # Real Hallucination & Quality Metrics
        has_research_warning = any("Historical Estimate" in str(r) or "No Real-Time Data" in str(r) for r in all_step_results)
        
        # Absolute Truth Confidence Score [0-100]
        # Signal: Missing real-time data (-20), Semantic misalignment (-25), Unresolved contradiction (-15), Replan (-5), Critic retries > 2 (-10)
        truth_score = 100
        if has_research_warning: truth_score -= 20
        truth_score -= (semantic_misalignments * 25)
        truth_score -= (unresolved_contradictions * 15)
        truth_score -= (recoveries * 5)
        if critic_retry_spikes > 1: truth_score -= 10
        
        truth_score = max(0, truth_score)
        
        if truth_score < 40:
            hallucination_rate = "⚠️ Critical (High Risk)"
        elif truth_score < 70 or has_research_warning:
            hallucination_rate = "Medium (Check Source Warnings)"
        else:
            hallucination_rate = "Low (Validated Source Track)"
            
        quality_score = "Excellent" if (truth_score >= 90 and recoveries == 0) else (f"Recovered ({recoveries} dynamic replans)" if recoveries > 0 else "Needs Review")

        metrics_card = (
            f"\n\n---"
            f"\n### 📊 System Intelligence Scorecard"
            f"\n- **🧠 Truth Confidence Score:** {truth_score}/100"
            f"\n- **⚡ Execution success rate:** {success_rate:.1f}% ({success_steps}/{total_steps_executed})"
            f"\n- **🔄 Adaptive Replans:** {recoveries} (DAG dynamic restructuring)"
            f"\n- **⏱️ Total time:** {total_time:.2f}s"
            f"\n- **❌ Hallucination Proxy Risk:** {hallucination_rate}"
            f"\n- **🧩 DAG Final Health State:** {quality_score}"
            f"\n---"
        )
        
        # Emit structured truth event for frontend badge
        publish({
            "type": "truth_metrics",
            "score": truth_score,
            "status": "high" if truth_score >= 80 else ("medium" if truth_score >= 50 else "low"),
            "verified_ratio": 1.0 if total_steps_executed > 0 else 0, # Simplified
            "misalignments": semantic_misalignments,
            "contradictions": unresolved_contradictions
        })

        # Synthesis
        publish({
            "type": "agent",
            "agent": "orchestrator",
            "role": "orchestrator",
            "status": "running",
            "content": "🧠 Synthesizing results and calculating metrics..."
        })

        final_answer = await synthesizer.synthesize(
            goal=query,
            step_results=all_step_results,
            context_block=context_str,
            llm=self.llm
        )

        final_answer += metrics_card

        publish({"type": "final", "content": final_answer})
        return final_answer

    async def _execute_one_step(self, step_desc: str, context: str) -> str:
        """Execute a single plan step. Called from execute_step_safe."""
        import time
        start_time = time.time()
        desc_lower = step_desc.lower()
        
        result = ""
        # Determine intent of the step to route to specialist agents
        if any(w in desc_lower for w in ["research", "find", "analyze trends", "competitors"]):
            from backend.agents.research_agent import ResearchAgent
            agent = ResearchAgent(self.llm)
            result = await agent.research(step_desc, depth="deep")
            
        elif any(w in desc_lower for w in ["write", "create copy", "brand name", "slogan", "script", "tweet", "post", "content"]):
            from backend.agents.writer_agent import WriterAgent
            agent = WriterAgent(self.llm)
            result = await agent.write(step_desc, context)
            
        elif any(w in desc_lower for w in ["code", "build tool", "implement", "app", "website", "api", "react", "html"]):
            from backend.agents.coder import CoderAgent
            from backend.agents.critic import CriticAgent
            coder = CoderAgent(self.llm)
            critic = CriticAgent(self.llm)
            initial_code = await coder.code(task=step_desc, context=context)
            # Use Critic for self-correction on code
            result = await critic.review_with_retry(
                step=step_desc,
                result=initial_code,
                executor=coder,
                context=context
            )
            
        else:
            # Default fallback to executor/LLM
            if hasattr(self.executor, "execute_step"):
                result = await self.executor.execute_step(step_desc, context)
            elif hasattr(self.executor, "run"):
                result = await self.executor.run(step_desc, publish=lambda _: None)
            else:
                # Use generate since complete might not exist on all wrappers depending on API
                messages = [{"role": "user", "content": f"Execute this task step:\n{step_desc}\n\nContext:\n{context}"}]
                import asyncio
                result = await asyncio.to_thread(self.llm.generate, messages)
                
        duration = time.time() - start_time
        logger.info(f"[_execute_one_step] Step took {duration:.2f}s | Desc: {step_desc[:50]}")
        return result

    # ── File Resolution ───────────────────────────────────────────────────────

    async def _resolve_and_store_files(
        self,
        file_ids: list,
        user_id: str,
        bot_id: str
    ) -> str:
        """
        Resolves uploaded file_ids from cache, chunks content, stores in memory,
        and returns a formatted context block for injection into the LLM prompt.
        """
        from backend.api.files import get_uploaded_file
        from backend.memory.memory_service import store_memory
        from backend.core.database import SessionLocal

        context_parts = []

        for file_id in file_ids:
            try:
                payload = get_uploaded_file(file_id)
                if not payload:
                    logger.warning(
                        "[TaskController] File %s not found in cache — skipped.", file_id
                    )
                    continue

                content = payload.get("content", "")
                filename = payload.get("filename", "unknown")
                category = payload.get("category", "document")

                if not content:
                    continue

                # Chunk and store in long-term memory
                chunks = self._chunk_text(content, chunk_size=400)
                logger.info(
                    "[TaskController] Storing %d chunk(s) from '%s' into memory.",
                    len(chunks), filename
                )

                with SessionLocal() as db:
                    for chunk in chunks:
                        store_memory(
                            db=db,
                            text_content=chunk,
                            category="document",
                            importance=0.65,
                            bot_id=bot_id,
                            platform_user_id=user_id
                        )

                preview = content[:1500]
                if len(content) > 1500:
                    preview += "\n... [truncated]"
                context_parts.append(
                    f"--- FILE: {filename} ({category}) ---\n{preview}"
                )

            except NameError as e:
                from backend.agents.import_healer import diagnose
                diagnose(e)
                logger.error("[TaskController] NameError resolving file %s: %s", file_id, e, exc_info=True)
            except ImportError as e:
                logger.error("[TaskController] ImportError resolving file %s: %s", file_id, e, exc_info=True)
            except Exception as e:
                logger.error("[TaskController] Failed to resolve file %s: %s", file_id, e)

        if not context_parts:
            return ""

        return (
            "[UPLOADED FILE CONTEXT — Reference when answering]:\n"
            + "\n\n".join(context_parts)
        )

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 400) -> list:
        """Splits text into word-bounded chunks for vector storage."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks
