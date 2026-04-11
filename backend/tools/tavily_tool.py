"""
backend/tools/tavily_tool.py
============================
Tavily-powered search tool for DreamAgent chat and orchestrator.
Falls back to DuckDuckGo if Tavily key is not set.

Supports:
  - General web search
  - News search  
  - Finance/market data search
  - Deep research mode
  - SEO analysis via Ahrefs
"""

import os
import logging
from typing import Any, Dict, Optional

from backend.tools.base import Tool

logger = logging.getLogger(__name__)


class TavilySearchTool(Tool):
    """
    Smart search tool: Tavily (if key set) → DuckDuckGo fallback.
    Used by the orchestrator for real-time data.
    """

    def run(self, query: str, topic: str = "general", depth: str = "basic", max_results: int = 5) -> str:
        """
        Execute a web search.

        Args:
            query: Search query
            topic: 'general', 'news', or 'finance'
            depth: 'basic' (fast) or 'advanced' (thorough)
            max_results: Number of results

        Returns:
            Formatted string with AI-synthesized answer + sources
        """
        if not query or len(query.strip()) < 3:
            return "Error: Query too short."

        # Try Tavily first
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        if tavily_key:
            result = self._tavily_search(query, tavily_key, topic=topic, depth=depth, max_results=max_results)
            if result and not result.startswith("Error"):
                return result

        # Fallback to DuckDuckGo
        return self._ddg_search(query)

    def _tavily_search(self, query: str, api_key: str, topic: str, depth: str, max_results: int) -> str:
        try:
            from integrations.tavily_client import TavilyClient
            tv = TavilyClient(api_key=api_key)
            if not tv.available:
                return ""

            data = tv.search(
                query=query,
                topic=topic,
                search_depth=depth,
                max_results=max_results,
                include_answer=True,
            )

            if "error" in data:
                logger.warning(f"[TavilyTool] Error: {data['error']}")
                return ""

            parts = []

            # AI-synthesized answer
            answer = data.get("answer", "").strip()
            if answer:
                parts.append(f"**Answer:** {answer}")

            # Source results
            results = data.get("results", [])
            if results:
                parts.append("\n**Sources:**")
                for r in results[:max_results]:
                    title = r.get("title", "")
                    url = r.get("url", "")
                    snippet = r.get("content", "")[:150]
                    if title and url:
                        parts.append(f"- [{title}]({url})\n  {snippet}...")

            return "\n".join(parts) if parts else ""

        except Exception as e:
            logger.warning(f"[TavilyTool] Exception: {e}")
            return ""

    def _ddg_search(self, query: str) -> str:
        """Fallback: DuckDuckGo Instant Answer API (no key required)."""
        try:
            import urllib.request
            import urllib.parse
            import json as _json

            encoded = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(url, headers={"User-Agent": "DreamAgent/2.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = _json.loads(resp.read().decode())

            abstract = data.get("AbstractText", "")
            answer = data.get("Answer", "")
            related = [r.get("Text", "") for r in data.get("RelatedTopics", [])[:3] if r.get("Text")]

            parts = []
            if abstract:
                parts.append(f"**Summary:** {abstract}")
            if answer:
                parts.append(f"**Answer:** {answer}")
            if related:
                parts.append("**Related:**\n" + "\n".join(f"- {r}" for r in related))

            return "\n\n".join(parts) if parts else f"No results found for: {query}"
        except Exception as e:
            return f"Search unavailable: {e}"


class TavilyNewsTool(Tool):
    """Dedicated news search tool using Tavily news topic."""

    def run(self, query: str) -> str:
        """Search for latest news on a topic."""
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        if not tavily_key:
            return self._rss_fallback(query)

        try:
            from integrations.tavily_client import TavilyClient
            tv = TavilyClient(api_key=tavily_key)
            if not tv.available:
                return self._rss_fallback(query)

            data = tv.search_news(query=query, max_results=6)
            if "error" in data:
                return self._rss_fallback(query)

            parts = [f"**Latest News: {query}**\n"]
            answer = data.get("answer", "").strip()
            if answer:
                parts.append(f"{answer}\n")

            results = data.get("results", [])
            for r in results:
                title = r.get("title", "Untitled")
                url = r.get("url", "#")
                date = r.get("published_date", "")
                snippet = r.get("content", "")[:120]
                date_str = f" _{date}_" if date else ""
                parts.append(f"**[{title}]({url})**{date_str}\n{snippet}...\n")

            return "\n".join(parts) if len(parts) > 1 else f"No news found for: {query}"
        except Exception as e:
            logger.warning(f"[TavilyNewsTool] Error: {e}")
            return self._rss_fallback(query)

    def _rss_fallback(self, query: str) -> str:
        """Minimal news fallback — just inform the user."""
        return (
            f"News search for '{query}' requires Tavily API key.\n"
            f"Add your Tavily key: tell me 'my tavily key is tvly-xxx' or add `TAVILY_API_KEY=...` to `.env`"
        )


class AhrefsSEOTool(Tool):
    """SEO analysis tool using Ahrefs API."""

    def run(self, domain_or_keyword: str, mode: str = "domain") -> str:
        """
        Perform an SEO lookup.

        Args:
            domain_or_keyword: Domain name or keyword to analyse
            mode: 'domain' for domain overview, 'keyword' for keyword data
        """
        ahrefs_key = os.getenv("AHREFS_API_KEY", "")
        if not ahrefs_key:
            return (
                f"Ahrefs SEO analysis requires an API key.\n"
                f"Add it via chat: 'my ahrefs key is <your-key>' or set `AHREFS_API_KEY` in `.env`"
            )

        try:
            from integrations.ahrefs_client import AhrefsClient
            ah = AhrefsClient(api_key=ahrefs_key)

            if mode == "domain":
                return ah.format_domain_report(domain_or_keyword)
            elif mode == "keyword":
                data = ah.keywords_explorer(domain_or_keyword)
                if "error" in data:
                    return f"**Ahrefs Error:** {data['error']}"
                kw_data = data.get("keywords", [{}])[0] if isinstance(data.get("keywords"), list) else data
                vol = kw_data.get("volume", "N/A")
                diff = kw_data.get("difficulty", "N/A")
                cpc = kw_data.get("cpc", "N/A")
                return (
                    f"**Keyword Analysis: `{domain_or_keyword}`**\n\n"
                    f"| Metric | Value |\n|---|---|\n"
                    f"| Search Volume | {vol} |\n"
                    f"| Keyword Difficulty | {diff}/100 |\n"
                    f"| CPC | ${cpc} |\n"
                )
            else:
                return f"Unknown mode '{mode}'. Use 'domain' or 'keyword'."
        except Exception as e:
            return f"Ahrefs lookup failed: {e}"
