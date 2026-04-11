"""
integrations/ahrefs_client.py

Ahrefs API v3 integration for DreamAgent.
Powers SEO analysis, backlink research, keyword data, and site audits.

Setup:
    pip install requests

Usage:
    from integrations.ahrefs_client import get_ahrefs
    ah = get_ahrefs()
    data = ah.domain_overview("example.com")
    kw   = ah.keywords_explorer("best ai tools")
"""

import os
import logging
from functools import lru_cache
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

_AHREFS_BASE = "https://api.ahrefs.com/v3"


class AhrefsClient:
    """
    Wrapper around the Ahrefs API v3.
    Requires a paid Ahrefs account with API access.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._available = bool(api_key)
        if self._available:
            logger.info("[Ahrefs] Client initialized.")
        else:
            logger.warning("[Ahrefs] AHREFS_API_KEY not set.")

    @property
    def available(self) -> bool:
        return self._available

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make an authenticated GET request to the Ahrefs API."""
        if not self._available:
            return {"error": "Ahrefs not available — AHREFS_API_KEY missing"}
        try:
            import requests  # type: ignore
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }
            url = f"{_AHREFS_BASE}/{endpoint}"
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[Ahrefs] API error on /{endpoint}: {e}")
            return {"error": str(e)}

    # ── Domain metrics ─────────────────────────────────────────────────

    def domain_overview(self, domain: str, country: str = "us") -> Dict[str, Any]:
        """
        Get key SEO metrics for a domain.

        Returns:
            Domain rating, organic traffic, backlinks, referring domains, etc.
        """
        return self._get("site-overview/overview", {
            "target": domain,
            "country": country,
            "protocol": "both",
        })

    def backlinks(self, domain: str, limit: int = 20, mode: str = "prefix") -> Dict[str, Any]:
        """
        Get top backlinks pointing to a domain/URL.

        Args:
            domain: Target domain or URL
            limit: Max number of backlinks (max 1000)
            mode: 'exact', 'prefix', 'domain', 'subdomains'
        """
        return self._get("site-explorer/backlinks", {
            "target": domain,
            "select": "url_from,url_to,domain_rating,ahrefs_rank,anchor,traffic",
            "limit": limit,
            "mode": mode,
            "order_by": "domain_rating:desc",
        })

    def referring_domains(self, domain: str, limit: int = 20) -> Dict[str, Any]:
        """Get referring domains for a target."""
        return self._get("site-explorer/referring-domains", {
            "target": domain,
            "select": "domain,domain_rating,backlinks,dofollow",
            "limit": limit,
            "order_by": "domain_rating:desc",
        })

    def top_pages(self, domain: str, country: str = "us", limit: int = 20) -> Dict[str, Any]:
        """Get top organic pages by estimated traffic."""
        return self._get("site-explorer/top-pages", {
            "target": domain,
            "country": country,
            "select": "url,traffic,keywords,top_keyword,top_keyword_volume",
            "limit": limit,
            "order_by": "traffic:desc",
        })

    def organic_keywords(self, domain: str, country: str = "us", limit: int = 30) -> Dict[str, Any]:
        """Get keywords a domain ranks for."""
        return self._get("site-explorer/organic-keywords", {
            "target": domain,
            "country": country,
            "select": "keyword,position,traffic,volume,keyword_difficulty,url",
            "limit": limit,
            "order_by": "traffic:desc",
        })

    # ── Keywords Explorer ──────────────────────────────────────────────

    def keywords_explorer(self, keyword: str, country: str = "us") -> Dict[str, Any]:
        """
        Get data for a specific keyword: search volume, difficulty, CPC, clicks.
        """
        return self._get("keywords-explorer/overview", {
            "select": "keyword,volume,difficulty,cpc,clicks,global_volume",
            "keywords": keyword,
            "country": country,
        })

    def keyword_ideas(self, keyword: str, country: str = "us", limit: int = 20) -> Dict[str, Any]:
        """Get keyword ideas/suggestions related to a seed keyword."""
        return self._get("keywords-explorer/also-rank-for", {
            "select": "keyword,volume,difficulty,cpc",
            "keyword": keyword,
            "country": country,
            "limit": limit,
            "order_by": "volume:desc",
        })

    def serp_overview(self, keyword: str, country: str = "us") -> Dict[str, Any]:
        """Get SERP overview for a keyword (who's ranking at top)."""
        return self._get("keywords-explorer/serp-overview", {
            "keyword": keyword,
            "country": country,
        })

    # ── Competitor Analysis ────────────────────────────────────────────

    def content_gap(self, target: str, competitors: List[str], country: str = "us", limit: int = 20) -> Dict[str, Any]:
        """
        Find keywords competitors rank for but the target doesn't.

        Args:
            target: Your domain
            competitors: List of competitor domains (max 5)
        """
        params: Dict[str, Any] = {
            "target": target,
            "country": country,
            "select": "keyword,volume,difficulty,best_position",
            "limit": limit,
        }
        for i, comp in enumerate(competitors[:5], start=1):
            params[f"compare_with[{i}]"] = comp
        return self._get("site-explorer/content-gap", params)

    def link_intersect(self, target: str, competitors: List[str], limit: int = 20) -> Dict[str, Any]:
        """
        Find domains linking to competitors but not to target.
        """
        params: Dict[str, Any] = {"target": target, "limit": limit}
        for i, comp in enumerate(competitors[:5], start=1):
            params[f"compare_with[{i}]"] = comp
        return self._get("site-explorer/link-intersect", params)

    # ── Rank Tracker ──────────────────────────────────────────────────

    def rank_tracker(self, domain: str, keywords: List[str], country: str = "us") -> Dict[str, Any]:
        """Track positions of specific keywords for a domain."""
        return self._get("rank-tracker/positions", {
            "target": domain,
            "keywords": ",".join(keywords),
            "country": country,
            "select": "keyword,current_position,max_title,traffic",
        })

    # ── Health check ──────────────────────────────────────────────────

    def ping(self) -> Dict[str, Any]:
        """Validate API key with a lightweight call."""
        if not self._available:
            return {"status": "unavailable", "reason": "AHREFS_API_KEY not set"}
        result = self._get("subscription-info/limits-and-usage", {})
        if "error" in result:
            return {"status": "error", "detail": result["error"]}
        return {"status": "ok", "info": result}

    # ── Formatted helpers for chat output ─────────────────────────────

    def format_domain_report(self, domain: str) -> str:
        """Returns a human-readable domain SEO report for chat display."""
        data = self.domain_overview(domain)
        if "error" in data:
            return f"**Ahrefs Error:** {data['error']}"
        
        metrics = data.get("domain", {}) or data
        dr = metrics.get("domain_rating", "N/A")
        traffic = metrics.get("org_traffic", metrics.get("traffic", "N/A"))
        backlinks = metrics.get("backlinks", "N/A")
        ref_domains = metrics.get("refdomains", metrics.get("referring_domains", "N/A"))

        return (
            f"**Ahrefs Report for `{domain}`**\n\n"
            f"| Metric | Value |\n"
            f"|---|---|\n"
            f"| Domain Rating (DR) | {dr} |\n"
            f"| Est. Organic Traffic | {traffic} |\n"
            f"| Total Backlinks | {backlinks} |\n"
            f"| Referring Domains | {ref_domains} |\n"
        )


@lru_cache(maxsize=1)
def get_ahrefs() -> AhrefsClient:
    """Get a singleton AhrefsClient from environment config."""
    api_key = os.getenv("AHREFS_API_KEY", "")
    if not api_key:
        logger.warning("[Ahrefs] AHREFS_API_KEY not set in .env — add it via chat or settings")
    return AhrefsClient(api_key=api_key)
