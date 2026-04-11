"""
integrations/tavily_client.py

Tavily Search API integration for DreamAgent.
Powers web search, news retrieval, and research pipelines.

Setup:
    pip install tavily-python

Usage:
    from integrations.tavily_client import get_tavily
    tv = get_tavily()
    results = tv.search("latest AI news")
"""

import os
import logging
from functools import lru_cache
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class TavilyClient:
    """
    Wrapper around the Tavily Python SDK.
    Falls back gracefully if tavily-python not installed.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        try:
            from tavily import TavilyClient as _TavilyClient  # type: ignore
            self._client = _TavilyClient(api_key=self.api_key)
            self._available = True
            logger.info("[Tavily] ✅ Tavily client initialized successfully.")
        except ImportError:
            logger.warning(
                "[Tavily] ⚠️  'tavily-python' package not installed. "
                "Run: pip install tavily-python"
            )
        except Exception as e:
            logger.error(f"[Tavily] ❌ Initialization failed: {e}")

    @property
    def available(self) -> bool:
        return self._available

    # ── Search helpers ─────────────────────────────────────────────────

    def search(
        self,
        query: str,
        search_depth: str = "basic",
        max_results: int = 5,
        include_answer: bool = True,
        include_images: bool = False,
        topic: str = "general",
    ) -> Dict[str, Any]:
        """
        Perform a Tavily web search.

        Args:
            query: Search query string
            search_depth: "basic" (fast) or "advanced" (deep research)
            max_results: Number of source results to return
            include_answer: Include AI-synthesized answer
            include_images: Include image results
            topic: "general", "news", or "finance"

        Returns:
            Dictionary with 'answer', 'results', and 'query' keys
        """
        if not self._available:
            return {"error": "Tavily not available", "results": [], "answer": ""}
        try:
            response = self._client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_answer=include_answer,
                include_images=include_images,
                topic=topic,
            )
            return {
                "query": query,
                "answer": response.get("answer", ""),
                "results": response.get("results", []),
                "images": response.get("images", []),
                "response_time": response.get("response_time", 0),
            }
        except Exception as e:
            logger.error(f"[Tavily] search error: {e}")
            return {"error": str(e), "results": [], "answer": ""}

    def search_news(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Shorthand for news-topic search."""
        return self.search(query=query, topic="news", max_results=max_results, search_depth="basic")

    def search_finance(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Shorthand for finance-topic search."""
        return self.search(query=query, topic="finance", max_results=max_results, search_depth="basic")

    def deep_research(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Advanced deep-research search."""
        return self.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
        )

    def get_urls(self, results: List[Dict]) -> List[str]:
        """Extract URL list from a search result set."""
        return [r.get("url", "") for r in results if r.get("url")]

    # ── Health check ──────────────────────────────────────────────────

    def ping(self) -> Dict[str, Any]:
        """Quick connectivity test via a minimal search."""
        if not self._available:
            return {"status": "unavailable", "reason": "tavily-python not installed or invalid key"}
        try:
            result = self.search("test connection", max_results=1, include_answer=False)
            if "error" in result:
                return {"status": "error", "detail": result["error"]}
            return {"status": "ok", "result_count": len(result.get("results", []))}
        except Exception as e:
            return {"status": "error", "detail": str(e)}


@lru_cache(maxsize=1)
def get_tavily() -> TavilyClient:
    """Get a singleton TavilyClient from environment config."""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        logger.warning("[Tavily] TAVILY_API_KEY not set in .env")
    return TavilyClient(api_key=api_key)
