"""
backend/agents/fast_orchestrator.py

High speed orchestrator for processing chat queries instantly.
Implements bounded responsibility: Rule-based routing -> Parallel Tool Ext -> Single LLM call.
"""
import logging
import json
from typing import AsyncGenerator, Dict, Any

from backend.llm.universal_provider import UniversalProvider
from backend.tools.fast_registry import fast_tools
from backend.core.final_formatter import format_final_response
from backend.core.background_worker import bg_worker

logger = logging.getLogger(__name__)

class FastOrchestrator:
    def __init__(self, provider: str = "auto", model: str = ""):
        self.llm = UniversalProvider(provider=provider, model=model)
        self.tools = fast_tools

    async def stream_handle(self, query: str, context: str = "") -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the query and yields dict events mapping to the two channels:
        Channel 1: 'status' UX updates ("Thinking...")
        Channel 2: 'final' format output (Response schema)
        """
        try:
            # 1. FAST INTENT (No LLM Call)
            yield {"event": "status", "message": "Detecting intent..."}
            intent_data = self._detect_intent_fast(query)

            # 2. RUN TOOLS IN PARALLEL
            tool_results = []
            if intent_data["use_tool"]:
                yield {"event": "status", "message": f"Calling tools: {','.join([t['tool'] for t in intent_data['tools']])}..."}
                tool_results = await self.tools.run_parallel(intent_data["tools"])
            
            # 3. SINGLE LLM CALL (CORE)
            yield {"event": "status", "message": "Synthesizing response..."}
            
            system_prompt = (
                "You are a fast, structured AI assistant.\n"
                "Provide a direct response based on the context and tool data provided.\n"
                "Do not format your response as JSON, return raw text."
            )
            
            user_prompt = f"Context:\n{context}\n\n"
            if tool_results:
                user_prompt += f"Tool Output Data:\n{json.dumps(tool_results, indent=2)}\n\n"
            user_prompt += f"User Query: {query}"
            
            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt
            )

            # 4. FINAL FORMAT (MANDATORY STRICT JSON)
            final_payload = format_final_response(
                status="success",
                resp_type="answer" if not tool_results else "tool",
                content=response,
                structured={"tool_results": tool_results} if tool_results else {}
            )
            
            yield {"event": "final", "data": final_payload}
            
            # 5. ASYNC BACKGROUND MEMORY (NON-BLOCKING)
            from backend.agents.memory_agent import MemoryAgent
            memory = MemoryAgent(self.llm)
            # Submit to background bounding queue to protect event loop
            await bg_worker.submit(memory.process_and_store(query))
            
        except Exception as e:
            logger.error(f"[FastOrchestrator] Execution failed: {e}", exc_info=True)
            yield {"event": "final", "data": format_final_response(
                status="error",
                resp_type="error",
                content="Something went wrong while processing the query.",
                error=str(e)
            )}

    def _detect_intent_fast(self, query: str) -> Dict[str, Any]:
        """Rule-based routing to keep orchestration dumb and extremely fast."""
        query_lower = query.lower()
        tools_to_run = []
        
        if "weather" in query_lower:
            tools_to_run.append({"tool": "weather", "input": query})
            
        if any(kw in query_lower for kw in ["search", "lookup", "news", "price", "latest", "today"]):
            tools_to_run.append({"tool": "search", "input": query})
            
        if tools_to_run:
            return {"use_tool": True, "tools": tools_to_run}
            
        return {"use_tool": False, "tools": []}
