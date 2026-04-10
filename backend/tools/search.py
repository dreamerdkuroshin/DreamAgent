"""
backend/tools/search.py — DuckDuckGo search tool with graceful fallback.
"""
import logging
import urllib.request
import urllib.parse
import json

from backend.tools.base import Tool

try:
    from langdetect import detect
except ImportError:
    def detect(text): return "en"

logger = logging.getLogger(__name__)

def get_user_language(query: str) -> str:
    try:
        return detect(query)
    except:
        return "en"

class SearchTool(Tool):
    def run(self, query: str) -> str:
        if not query or len(query.strip()) < 3:
            return "Error: Query too short."

        try:
            # Use DuckDuckGo Instant Answer API (no API key required)
            encoded = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(url, headers={"User-Agent": "DreamAgent/2.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            abstract = data.get("AbstractText", "")
            answer = data.get("Answer", "")
            
            user_lang = get_user_language(query)
            filtered_related = []
            for r in data.get("RelatedTopics", []):
                text = r.get("Text", "")
                if not text:
                    continue
                try:
                    res_lang = detect(text)
                except:
                    res_lang = "en"
                    
                if res_lang == user_lang or res_lang == "en":
                    filtered_related.append(text)
                    if len(filtered_related) >= 3:
                        break

            parts = []
            if abstract:
                parts.append(f"Summary: {abstract}")
            if answer:
                parts.append(f"Answer: {answer}")
            if filtered_related:
                parts.append("Related:\n" + "\n".join(f"- {r}" for r in filtered_related))

            return "\n\n".join(parts) if parts else f"No results found for: {query}"
        except Exception as e:
            logger.warning(f"[SearchTool] Failed: {e}")
            return f"Search unavailable: {str(e)}"
