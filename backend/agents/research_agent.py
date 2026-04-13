"""
backend/agents/research_agent.py

ResearchAgent — Specialized for fact-finding, retrieving real-time data, and summarizing trends.
Wraps Tavily web search. If unavailable, falls back to LLM knowledge.
"""
import logging
from typing import Optional
from .base_agent import BaseAgent
import os

logger = logging.getLogger(__name__)

RESEARCH_SYSTEM = """You are a highly capable Research Agent.
Your goal is to extract facts, analyze trends, discover competitors, and synthesize complex information.

Guidelines:
1. Provide accurate, data-driven insights. Ground your answer in the provided search data.
2. CITATION MANDATE: Every factual claim MUST be followed by its source inline as [Source: URL]. You MUST only use URLs provided in the web search data.
3. Do not invent facts or fake URLs. If information is missing, explicitly state "Data unavailable".
4. When asked about competitors or trends, categorize them logically.
"""

class ResearchAgent(BaseAgent):
    """
    Fact-finding and analysis agent. Uses web search if a tool for it exists.
    """

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools, role="research")

    async def _safe_search(self, query: str) -> str:
        """Call Tavily search if apiKey exists, else return empty string."""
        import os
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return ""
            
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = "https://api.tavily.com/search"
                payload = {
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "max_results": 4
                }
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        answer = data.get("answer", "")
                        results = "\\n".join([f"- {r.get('title')} ({r.get('url', 'no-url')}): {r.get('content')}" for r in data.get("results", [])])
                        return f"Search Summary:\\n{answer}\\n\\nSearch Results:\\n{results}"
        except Exception as e:
        return ""
        
    async def _verify_semantics(self, claim: str, snippets: str) -> dict:
        """
        Independent LLM pass to verify claim against raw search data.
        """
        judge_system = "You are a Semantic Alignment Judge. Your job is to verify if a claim is directly supported by raw search results. Return JSON: {status: 'aligned'|'misaligned', confidence: 0.1-1.0, reason: string}"
        prompt = f"CLAIM: {claim}\n\nRAW SOURCE DATA:\n{snippets}\n\nVerify the claim. Be strict."
        try:
            resp = await self.think(prompt, system=judge_system)
            import json
            # Extract JSON from potential markdown markers
            if "```json" in resp:
                resp = resp.split("```json")[1].split("```")[0].strip()
            elif "{" in resp:
                resp = "{" + resp.split("{", 1)[1].rsplit("}", 1)[0] + "}"
                
            return json.loads(resp)
        except Exception as e:
            logger.error(f"[SemanticJudge] Verification failed: {e}")
            return {"status": "error", "reason": str(e)}

    # Local cache for semantic checks: hash(claim+source) -> dict
    _semantic_cache = {}

    async def research(self, topic: str, depth: str = "shallow", trust_mode: str = "fast") -> str:
        """
        Conduct research on the given topic.
        """
        logger.info(f"[ResearchAgent] Researching topic: {topic[:50]}... (depth: {depth})")
        
        search_context = ""
        # Check if we should search
        needs_search = any(k in topic.lower() for k in ["recent", "latest", "news", "trend", "competitor", "viral", "days"])
        if needs_search:
            logger.info("[ResearchAgent] Topic requires real-time data. Triggering search.")
            search_context = await self._safe_search(topic)
            
        prompt = (
            f"RESEARCH TOPIC:\n{topic}\n\n"
            f"DEPTH:\n{depth}\n\n"
        )
        
        if search_context:
            prompt += f"WEB SEARCH DATA:\n{search_context}\n\nGround your analysis strictly on this data and include [Source: URL] citations."
        else:
            prompt += "No recent web data available. Rely on your base knowledge to structure an analysis."
            
        start_time = None
        import time
        start_time = time.time()
        
        result = await self.think(prompt, system=RESEARCH_SYSTEM)
        
        if not search_context and needs_search:
            result = f"**[⚠️ WARNING: No Real-Time Data Available - Output is historical estimate]**\n\n{result}"
            
        # Semantic Alignment Layer (Truth Mode)
        if trust_mode == "truth" and search_context:
            import re
            import hashlib
            # extract claims with citations: "Claim [Source: URL]"
            patterns = re.findall(r'([^.!?\n]+\[Source: [^\]]+\])', result)
            
            # Heuristic: Selective Verification (numbers, superlatives, strong assertions)
            HIGH_IMPACT_KEYWORDS = ["%", "best", "leading", "most", "increase", "decrease", "million", "billion", "only", "first", "last"]
            
            verification_tasks = []
            claims_to_check = []
            
            for claim_segment in patterns:
                segment_lower = claim_segment.lower()
                if any(kw in segment_lower for kw in HIGH_IMPACT_KEYWORDS) or len(segment_lower) > 60:
                    cache_key = hashlib.md5(f"{claim_segment}:{search_context[:500]}".encode()).hexdigest()
                    if cache_key in self._semantic_cache:
                        msg = self._semantic_cache[cache_key]
                        if msg.get("status") == "misaligned":
                            result = result.replace(claim_segment, f"{claim_segment} [⚠️ Source does not support claim: {msg.get('reason')}]")
                    else:
                        claims_to_check.append((claim_segment, cache_key))
                        verification_tasks.append(self._verify_semantics(claim_segment, search_context))
            
            if verification_tasks:
                import asyncio
                # In parallel to DAG (for simulation, here we wait as it's inside the agent)
                judgments = await asyncio.gather(*verification_tasks)
                for (claim, cache_key), judge in zip(claims_to_check, judgments):
                    self._semantic_cache[cache_key] = judge
                    if judge.get("status") == "misaligned":
                        result = result.replace(claim, f"{claim} [⚠️ Source does not support claim: {judge.get('reason')}]")

        duration = time.time() - start_time
        logger.info(f"[ResearchAgent] Completed in {duration:.2f}s (mode: {trust_mode})")
        return result
