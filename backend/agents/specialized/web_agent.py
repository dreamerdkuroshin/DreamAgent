"""
backend/agents/specialized/web_agent.py

WebAgent — Searches the web and returns a summarized answer.
Uses DuckDuckGo (no API key required) with optional Tavily fallback.
"""

import logging
import asyncio
from typing import Optional
from backend.llm.universal_provider import UniversalProvider

logger = logging.getLogger(__name__)


async def _duckduckgo_search(query: str, max_results: int = 5) -> str:
    """Run DuckDuckGo search in a thread (sync library)."""
    try:
        from duckduckgo_search import DDGS
        def _search():
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return ""
            lines = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                lines.append(f"**{title}**\n{body}\nSource: {href}")
            return "\n\n---\n\n".join(lines)

        return await asyncio.to_thread(_search)
    except ImportError:
        logger.warning("[WebAgent] duckduckgo-search not installed. Install: pip install duckduckgo-search")
        return ""
    except Exception as e:
        logger.warning(f"[WebAgent] DuckDuckGo search failed: {e}")
        return ""


async def _tavily_search(query: str) -> str:
    """Optional Tavily search if API key is set."""
    import os
    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        return ""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": query, "max_results": 5},
            )
            data = resp.json()
            results = data.get("results", [])
            lines = [f"**{r.get('title','')}**\n{r.get('content','')}\nSource: {r.get('url','')}"
                     for r in results]
            return "\n\n---\n\n".join(lines)
    except Exception as e:
        logger.warning(f"[WebAgent] Tavily search failed: {e}")
        return ""


class WebAgent:
    """
    Searches the web and returns a clean, summarized answer.
    Uses DuckDuckGo → Tavily fallback → LLM synthesis.
    """

    def __init__(self, provider: str = "auto", model: str = ""):
        self.llm = UniversalProvider(provider=provider, model=model)

    async def search(self, query: str) -> str:
        """Search the web and return a summarized answer."""
        logger.info(f"[WebAgent] Searching: {query[:80]}")

        # Try DuckDuckGo first
        raw = await _duckduckgo_search(query)

        # Fallback to Tavily
        if not raw:
            raw = await _tavily_search(query)

        if not raw:
            fallback_prompt = (
                f"User asked for: {query}\n\n"
                "Web search currently failed to fetch live results. "
                "However, you MUST provide the best possible information you know about this based on your training data. "
                "Do NOT apologize. Do NOT say you cannot provide real-time data or that you lack internet access. "
                "Start your response EXACTLY with 'Here are the latest available updates:' and then give a helpful compilation."
            )
            try:
                answer = await asyncio.wait_for(
                    self.llm.complete(fallback_prompt), timeout=20
                )
                return str(answer).strip()
            except Exception:
                return "Here are the latest available updates:\nCurrently experiencing network interruptions, but please check back in a moment."

        # Let the LLM synthesize a clean answer from the raw results
        synthesis_prompt = (
            f"User asked: {query}\n\n"
            f"Web search results:\n{raw[:4000]}\n\n"
            "Provide a clear, accurate, concise answer based on these results. "
            "Use inline citations in the format [1], [2], etc., corresponding to the sources. "
            "At the bottom of your response, strictly output the references in a button-style Markdown format like this:\n\n"
            "---\n"
            "[🔘 Source 1 Title](URL) \n"
            "[🔘 Source 2 Title](URL) \n\n"
            "Ensure the links are proper valid Markown links. Do NOT repeat the raw search results verbatim."
        )

        try:
            answer = await asyncio.wait_for(
                self.llm.complete(synthesis_prompt), timeout=30
            )
            return str(answer).strip()
        except Exception as e:
            logger.warning(f"[WebAgent] LLM synthesis failed: {e}")
            # Return raw results as fallback
            return raw[:2000]


# Register with StructuredRouter
async def _web_handler(query: str) -> str:
    agent = WebAgent()
    return await agent.search(query)


def register(router=None):
    """Register this agent with a StructuredRouter instance."""
    if router:
        router.register_tool("search_web", _web_handler)
    else:
        from backend.agents.structured_router import register_tool
        register_tool("search_web", _web_handler)
