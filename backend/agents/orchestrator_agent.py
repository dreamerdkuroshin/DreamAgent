"""
backend/agents/orchestrator_agent.py

Orchestrator (MAIN BRAIN)
Coordinates Planner, Memory, Tool, and Executor Agents autonomously.
"""
import logging
import asyncio
import time
from typing import Dict, Any, Callable

from backend.memory.vector_db import vector_db

def should_use_rag(query: str, file_ids: list = None) -> bool:
    """Smart RAG trigger to prevent unnecessary vector searches."""
    if file_ids and len(file_ids) > 0:
        return True

    keywords = ["document", "pdf", "file", "notes", "summarize", "codebase", "contract"]
    return any(k in query.lower() for k in keywords)

logger = logging.getLogger(__name__)

class Orchestrator:
    """The central brain routing user queries to appropriate specialized agents."""
    
    def __init__(self, planner_agent, memory_agent, tool_agent, executor_agent):
        self.planner = planner_agent
        self.memory = memory_agent
        self.tool = tool_agent
        self.executor = executor_agent

    async def run(
        self, 
        user_input: str, 
        publish: Callable[[Dict[str, Any]], None], 
        bot_id: str = None, 
        platform_user_id: str = None
    ) -> str:
        
        logger.info(f"[Orchestrator] Processing query for Bot: {bot_id} | User: {platform_user_id}")
        
        # 🧠 Smart Execution Mode Flag (AutoGPT bypass)
        def detect_mode(prompt: str):
            prompt_lower = prompt.lower()
            if "do this task" in prompt_lower or "automate" in prompt_lower or "loop" in prompt_lower:
                return "autonomous"
            return "chat"
            
        mode = detect_mode(user_input)
        
        if mode == "autonomous":
            publish({
                "type": "agent", "agent": "orchestrator", "role": "system",
                "status": "running", "content": "🤖 Autonomous Mode detected. Launching Task Engine..."
            })
            
            from backend.agents.autonomous.autonomous_manager import AutonomousManager
            from backend.agents.autonomous.event_adapter import to_chat_event
            from backend.llm.universal_provider import universal_provider
            
            manager = AutonomousManager(provider=universal_provider)
            final_eval = ""
            
            async for event in manager.stream(platform_user_id, bot_id, user_input):
                chat_payload = to_chat_event(event)
                publish(chat_payload)
                
                # Capture evaluation text if it arrives
                if event.get("type") == "final":
                    final_eval = str(event.get("data", {}).get("final_evaluation", ""))
            
            # Close out the stream nicely so the frontend stops waiting
            publish({
                "type": "agent", "agent": "orchestrator", "role": "system",
                "status": "done", "content": f"✅ Engine finished."
            })
            
            return f"**Autonomous Task Cycle Completed:**\n{final_eval}"

        
        # 1. Proactive Memory Extraction & Storage (async to keep it extremely fast)
        publish({
            "type": "agent", "agent": "memory", "role": "memory",
            "status": "running", "content": "🧠 Scanning input for core memory facts..."
        })
        
        # We fire the background task so it doesn't block the actual generation of the chat.
        # But wait, we should do it immediately before building context to ensure "my name is X" is available.
        await self.memory.process_and_store(
            user_input, 
            bot_id=bot_id, 
            platform_user_id=platform_user_id
        )

        publish({
            "type": "agent", "agent": "memory", "role": "memory",
            "status": "done", "content": "✨ Core memory linked."
        })

        # 2. Context Retrieval (Standard DB memory)
        context = await self.memory.get_context(
            user_input, 
            bot_id=bot_id, 
            platform_user_id=platform_user_id
        )

        import re
        file_ids_match = re.search(r"IDs: ([a-zA-Z0-9_\-,]+)", user_input)
        file_ids = [fid.strip() for fid in file_ids_match.group(1).split(",") if fid.strip()] if file_ids_match else []

        # ── 2.2  Direct File Content Injection + Smart Routing ──────────────
        # Fetch uploaded file payloads from Redis/memory store (secure, token-budgeted)
        uploaded_docs = []
        if file_ids:
            try:
                from backend.api.files import get_uploaded_file
                from backend.services.file_processor import FileResult, build_file_context
                for fid in file_ids:
                    payload = get_uploaded_file(fid)
                    if payload:
                        uploaded_docs.append(payload)

                if uploaded_docs:
                    # Smart routing: if ALL files are the same category, hand off to a specialist
                    categories = {d["category"] for d in uploaded_docs}
                    specialist_result = None

                    if categories == {"code"}:
                        publish({
                            "type": "agent", "agent": "code", "role": "system",
                            "status": "running",
                            "content": "🔬 Code files detected — routing to Code Agent...",
                        })
                        try:
                            from backend.agents.specialized.code_agent import CodeAgent
                            from backend.llm.universal_provider import UniversalProvider
                            _code_llm = UniversalProvider()
                            agent = CodeAgent(llm=_code_llm)
                            combined = "\n\n".join(
                                f"[FILE: {d['filename']}]\n{d['content']}"
                                for d in uploaded_docs
                            )
                            specialist_result = await agent.execute(
                                step=f"{user_input}\n\nCode:\n{combined}",
                                context=""
                            )
                        except Exception as e:
                            logger.warning(f"[Orchestrator] CodeAgent failed: {e}")

                    elif categories == {"data"} or categories == {"spreadsheet"}:
                        publish({
                            "type": "agent", "agent": "file", "role": "system",
                            "status": "running",
                            "content": "📊 Data files detected — routing to Data Analysis Agent...",
                        })
                        # Compose a data-focused prompt for the standard executor path
                        combined = "\n\n".join(
                            f"[FILE: {d['filename']} ({d['category']})]\n{d['content']}"
                            for d in uploaded_docs
                        )
                        context = (
                            f"{context}\n\n"
                            f"[DATA ANALYSIS CONTEXT — treat the following as structured data to analyse]\n"
                            f"{combined}"
                        )
                        publish({
                            "type": "agent", "agent": "file", "role": "system",
                            "status": "done",
                            "content": f"📎 {len(uploaded_docs)} data file(s) loaded for analysis.",
                        })

                    else:
                        # Mixed or other category — merge with budget into general context
                        file_results = [
                            FileResult(
                                file_id=d["file_id"],
                                filename=d["filename"],
                                file_type=d["file_type"],
                                category=d["category"],
                                content_text=d["content"],
                                raw_preview=d.get("raw_preview", ""),
                                metadata=d.get("metadata", {}),
                            )
                            for d in uploaded_docs
                        ]
                        merged = build_file_context(file_results)
                        context = f"{context}\n\n[Attached File Contents]:\n{merged}"
                        publish({
                            "type": "agent", "agent": "memory", "role": "memory",
                            "status": "done",
                            "content": f"📎 {len(uploaded_docs)} file(s) merged into context.",
                        })

                    # If a specialist produced a final result, skip the rest of
                    # the orchestrator pipeline and surface it directly
                    if specialist_result:
                        publish({"type": "final", "content": specialist_result})
                        return specialist_result

            except Exception as e:
                logger.error(f"[Orchestrator] File injection failed: {e}", exc_info=True)


        # 2.5 Optional Phase 4 Magic RAG Injection
        if should_use_rag(user_input, file_ids):
            publish({
                "type": "agent", "agent": "memory", "role": "memory",
                "status": "running", "content": "🔍 Searching vector database for relevant documents..."
            })
            
            # Dynamic Top-K: Scale context width based on query intent
            if len(user_input.split()) < 4:
                dynamic_top_k = 3
            elif "summarize" in user_input.lower() or "summary" in user_input.lower():
                dynamic_top_k = 8
            else:
                dynamic_top_k = 5
            
            try:
                # Need to look up the specific bot's current embedded provider setting
                from backend.core.database import SessionLocal
                from backend.core.models import Bot
                db_session = SessionLocal()
                try:
                    bot = db_session.query(Bot).filter(Bot.id == bot_id).first()
                    provider = bot.embedding_provider if bot else "local"
                finally:
                    db_session.close()

                # Lazy import to avoid loading models if not needed globally
                from backend.llm.embedding_provider import get_embedding
                
                start_embed = time.time()
                query_embedding = await get_embedding(user_input, provider=provider)
                embed_time_ms = int((time.time() - start_embed) * 1000)
                
                if query_embedding:
                    # RAG MUST have a timeout per requirements
                    start_search = time.time()
                    results = await asyncio.wait_for(
                        asyncio.to_thread(
                            vector_db.search,
                            embedding=query_embedding,
                            bot_id=bot_id,
                            user_id=platform_user_id,
                            provider=provider,
                            file_ids=file_ids,
                            top_k=dynamic_top_k
                        ),
                        timeout=5.0
                    )
                    
                    if results:
                        search_time_ms = int((time.time() - start_search) * 1000)
                        
                        print(f"[RAG METRICS]\nquery_time: {search_time_ms}ms\nembedding_time: {embed_time_ms}ms\nresults: {len(results)}\nprovider: {provider}\n")
                        
                        # Hard Token Budget (~1500 tokens roughly maps to 6000 chars)
                        MAX_TOKENS_CHARS = 6000
                        current_len = 0
                        final_chunks = []
                        
                        for chunk in results:
                            if current_len + len(chunk) > MAX_TOKENS_CHARS:
                                break
                            final_chunks.append(chunk)
                            current_len += len(chunk)
                        
                        context_header = "Context:\n" + "\n".join([f"[{i+1}] {chunk}" for i, chunk in enumerate(final_chunks)])
                        context_header += "\n\nInstructions:\nUse ONLY the above context if relevant."
                            
                        # Prepend RAG chunks to existing DB context
                        context = f"{context_header}\n\n[Standard Chat Context]:\n{context}"
                        
                        publish({
                            "type": "agent", "agent": "memory", "role": "memory",
                            "status": "done", "content": f"✅ Injected {len(final_chunks)} highly relevant document chunks."
                        })
                    else:
                        publish({
                            "type": "agent", "agent": "memory", "role": "memory",
                            "status": "done", "content": "⚠️ No relevant document chunks found in search."
                        })
            except asyncio.TimeoutError:
                publish({
                    "type": "agent", "agent": "memory", "role": "memory",
                    "status": "error", "content": "❌ Vector search timed out."
                })
                print("[RAG] Search timed out.")
            except Exception as e:
                print(f"[RAG] Search failed: {e}")

        # 3. Conditional Planning
        publish({
            "type": "plan", "agent": "planner", "role": "planner",
            "status": "running", "content": "🧠 Planner evaluating execution strategy..."
        })
        
        plan_data = await self.planner.plan(user_input)
        
        # Fast Path Bypass
        if not plan_data.get("requires_plan"):
            publish({
                "type": "plan", "agent": "planner", "role": "planner",
                "status": "skipped", "content": "⚡ Direct factual query detected. Bypassing autonomous loop."
            })
            
            publish({
                "type": "agent", "agent": "executor", "role": "executor",
                "status": "running", "content": "💬 Formatting direct response."
            })
            
            # Execute "fast" directly
            return await self.executor.execute(
                step=f"Answer the user query concisely: {user_input}", 
                context=context
            )
            
        # Full Autonomous Execution
        steps = plan_data.get("steps", [])
        publish({
            "type": "plan", "agent": "planner", "role": "planner",
            "status": "done", "content": f"📋 Multi-Step Plan Generated ({len(steps)} steps):\n" + "\n".join(f"{i+1}. {s}" for i,s in enumerate(steps))
        })
        
        step_results = []
        for idx, step in enumerate(steps):
            publish({
                "type": "agent", "agent": "executor", "role": "executor",
                "status": "running", "step": idx, "content": f"⚡ Executing step {idx+1}/{len(steps)}: {step}"
            })
            
            # If the step clearly instructs using a tool (e.g. web search), we would invoke tool_agent.
            # For this simplified abstraction, the LLM executor decides or acts as a proxy.
            # Let's execute the step:
            ctx_bundle = context + "\n\n[Previous Step Results]:\n" + "\n".join(step_results)
            result = await self.executor.execute(step, context=ctx_bundle)
            step_results.append(f"Step {idx+1}: {result}")
            
            publish({
                "type": "agent", "agent": "executor", "role": "executor",
                "status": "done", "step": idx, "content": f"✅ Completed step {idx+1}."
            })

        # Final Synthesis
        publish({
            "type": "agent", "agent": "orchestrator", "role": "orchestrator",
            "status": "running", "content": "🧠 Synthesizing final multi-agent execution map."
        })
        
        final_prompt = f"Original Goal: {user_input}\nContext:\n{context}\n\nSteps Completed:\n" + "\n".join(step_results) + "\n\nProvide the final output to the user clearly."
        final_answer = await self.executor.think(final_prompt)
        
        return final_answer
