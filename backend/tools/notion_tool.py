"""
backend/tools/notion_tool.py

Real Notion API integration for DreamAgent.
Features:
  - Create learning tracker pages (concept + exercises + progress)
  - Append notes / progress updates to existing pages
  - Search pages in the workspace
  - Read page content
  - Update progress status on learning pages

Uses the OAuth access_token stored after the user authorizes Notion.
Falls back to NOTION_ACCESS_TOKEN env var for manual token entry.
"""

import os
import json
import logging
import httpx
from typing import Any, Dict, List, Optional
from backend.orchestrator.retry_handler import with_retry

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION  = "2022-06-28"


# ─── Token Resolution ────────────────────────────────────────────────────────

def _get_access_token(user_id: str = "local_user", bot_id: str = "local_bot") -> Optional[str]:
    """Retrieve the stored Notion OAuth access token."""
    # 1. Try DB OAuth token first (set via OAuth flow)
    try:
        from backend.oauth.oauth_manager import get_active_token
        import asyncio
        token = asyncio.run(get_active_token(user_id, bot_id, "notion"))
        if token:
            return token
    except Exception as e:
        logger.debug(f"[NotionTool] DB token lookup failed: {e}")

    # 2. Fall back to env var (manual token pasted by user)
    return os.getenv("NOTION_ACCESS_TOKEN") or None


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ─── Core API Helpers ────────────────────────────────────────────────────────

def _get(path: str, token: str) -> Dict:
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{NOTION_API_BASE}{path}", headers=_headers(token))
        resp.raise_for_status()
        return resp.json()


def _post(path: str, body: Dict, token: str) -> Dict:
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{NOTION_API_BASE}{path}", headers=_headers(token), json=body)
        resp.raise_for_status()
        return resp.json()


def _patch(path: str, body: Dict, token: str) -> Dict:
    with httpx.Client(timeout=30) as client:
        resp = client.patch(f"{NOTION_API_BASE}{path}", headers=_headers(token), json=body)
        resp.raise_for_status()
        return resp.json()


# ─── Block Builders ──────────────────────────────────────────────────────────

def _heading(text: str, level: int = 2) -> Dict:
    return {
        "object": "block",
        "type": f"heading_{level}",
        f"heading_{level}": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def _paragraph(text: str) -> Dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def _callout(text: str, emoji: str = "💡") -> Dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "icon": {"type": "emoji", "emoji": emoji}
        }
    }


def _divider() -> Dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _numbered_item(text: str) -> Dict:
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def _bullet(text: str) -> Dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def _todo(text: str, checked: bool = False) -> Dict:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "checked": checked
        }
    }


# ─── Public Tool Functions ───────────────────────────────────────────────────

def create_learning_tracker(
    topic: str,
    explanation: str,
    exercises: List[str],
    parent_page_id: Optional[str] = None,
    user_id: str = "local_user",
    bot_id: str = "local_bot",
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a full learning tracker page in Notion with:
    - Concept explanation
    - Numbered exercises
    - Progress tracking checklist

    Returns: { "success": bool, "page_url": str, "page_id": str, "message": str }
    """
    token = _get_access_token(user_id, bot_id)
    if not token:
        return {
            "success": False,
            "action": "reauth_required",
            "provider": "notion",
            "message": "No Notion access token found. Please authorize Notion first by clicking the auth link.",
            "page_url": None
        }

    # 1. Tool-Level Idempotency Check
    from backend.core.execution_context import get_execution_id
    effective_idem_key = idempotency_key or get_execution_id()
    
    if effective_idem_key:
        from backend.core.task_queue import redis_conn
        if redis_conn:
            cached = redis_conn.get(f"idem:notion:{effective_idem_key}")
            if cached:
                logger.info(f"[NotionTool] Idempotency Hit: Returning cached page for {effective_idem_key}")
                return json.loads(cached)


    # Build page parent
    if parent_page_id:
        parent = {"type": "page_id", "page_id": parent_page_id}
    else:
        # Use workspace root (requires integration to have workspace access)
        parent = {"type": "workspace", "workspace": True}

    # Build page content blocks
    blocks = [
        _callout(f"Learning topic: {topic}", "🎓"),
        _divider(),

        _heading("📖 Concept Explanation", level=2),
        _paragraph(explanation),
        _divider(),

        _heading("✏️ Practice Exercises", level=2),
    ]

    for i, ex in enumerate(exercises, 1):
        blocks.append(_numbered_item(ex))

    blocks += [
        _divider(),
        _heading("📊 Progress Tracker", level=2),
        _todo("Read and understand the concept", checked=False),
        _todo("Complete Exercise 1", checked=False),
        _todo("Complete Exercise 2", checked=False),
        _todo("Complete Exercise 3", checked=False),
        _todo("Review and revisit if needed", checked=False),
        _divider(),
        _paragraph(f"Created by DreamAgent | Topic: {topic}"),
    ]

    # Page properties
    properties = {
        "title": {
            "title": [{"type": "text", "text": {"content": f"Learning: {topic}"}}]
        }
    }

    body = {
        "parent": parent,
        "icon": {"type": "emoji", "emoji": "🧠"},
        "cover": {
            "type": "external",
            "external": {"url": "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8"}
        },
        "properties": properties,
        "children": blocks[:100],  # Notion API limit: 100 blocks per request
    }

    try:
        # 2. Wrapped Post with Retry/Rate-limit awareness
        async def _do_post():
            return _post("/pages", body, token)
            
        result = await with_retry("notion", _do_post)
        
        # Intercept retry signal from handler
        if isinstance(result, dict) and result.get("action") == "retry_later":
            return result
            
        page_id  = result.get("id", "")
        page_url = result.get("url", "")
        logger.info(f"[NotionTool] Created learning tracker: {page_url}")
        
        res_payload = {
            "success": True,
            "page_id": page_id,
            "page_url": page_url,
            "message": f"Learning tracker for '{topic}' created in Notion!",
        }
        
        # Store for idempotency
        if effective_idem_key:
            from backend.core.task_queue import redis_conn
            if redis_conn:
                redis_conn.setex(f"idem:notion:{effective_idem_key}", 86400, json.dumps(res_payload))
                
        return res_payload
    except httpx.HTTPStatusError as e:
        err = e.response.text
        logger.error(f"[NotionTool] API error: {err}")
        if e.response.status_code == 401:
            return {
                "success": False, 
                "action": "reauth_required",
                "provider": "notion",
                "message": "Notion token expired or invalid. Please re-authorize."
            }
        if e.response.status_code == 403:
            return {"success": False, "message": "Notion integration lacks permission. Please share a page with the integration in Notion settings."}
        return {"success": False, "message": f"Notion API error: {err}"}
    except Exception as e:
        logger.error(f"[NotionTool] Unexpected error: {e}", exc_info=True)
        return {"success": False, "message": f"Error: {str(e)}"}


def update_progress(
    page_id: str,
    completed_exercise: int,
    user_id: str = "local_user",
    bot_id: str = "local_bot",
) -> Dict[str, Any]:
    """
    Append a progress update block to an existing Notion learning tracker page.
    """
    token = _get_access_token(user_id, bot_id)
    if not token:
        return {
            "success": False, 
            "action": "reauth_required",
            "provider": "notion",
            "message": "No Notion access token."
        }

    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    block = _callout(
        f"[{ts}] Exercise {completed_exercise} marked complete!",
        emoji="✅"
    )

    try:
        _patch(f"/blocks/{page_id}/children", {"children": [block]}, token)
        return {"success": True, "message": f"Progress updated: exercise {completed_exercise} done."}
    except Exception as e:
        return {"success": False, "message": f"Update failed: {e}"}


def search_pages(query: str, user_id: str = "local_user", bot_id: str = "local_bot") -> Dict[str, Any]:
    """Search for pages in the Notion workspace."""
    token = _get_access_token(user_id, bot_id)
    if not token:
        return {
            "success": False, 
            "results": [], 
            "action": "reauth_required",
            "provider": "notion",
            "message": "No Notion access token."
        }

    try:
        result = _post("/search", {"query": query, "filter": {"value": "page", "property": "object"}}, token)
        pages = []
        for item in result.get("results", []):
            title_prop = item.get("properties", {}).get("title", {})
            title_parts = title_prop.get("title", [])
            title = "".join(p.get("plain_text", "") for p in title_parts) if title_parts else "(Untitled)"
            pages.append({
                "id": item.get("id"),
                "title": title,
                "url": item.get("url"),
                "last_edited": item.get("last_edited_time"),
            })
        return {"success": True, "results": pages, "count": len(pages)}
    except Exception as e:
        return {"success": False, "results": [], "message": f"Search failed: {e}"}


def get_page_content(page_id: str, user_id: str = "local_user", bot_id: str = "local_bot") -> Dict[str, Any]:
    """Read all text blocks from a Notion page."""
    token = _get_access_token(user_id, bot_id)
    if not token:
        return {
            "success": False, 
            "content": "", 
            "action": "reauth_required",
            "provider": "notion",
            "message": "No Notion access token."
        }

    try:
        result = _get(f"/blocks/{page_id}/children", token)
        lines = []
        for block in result.get("results", []):
            btype = block.get("type", "")
            bdata = block.get(btype, {})
            rich  = bdata.get("rich_text", [])
            text  = "".join(r.get("plain_text", "") for r in rich)
            if text:
                lines.append(text)
        return {"success": True, "content": "\n".join(lines)}
    except Exception as e:
        return {"success": False, "content": "", "message": f"Read failed: {e}"}


# ─── LLM-Assisted Learning Tracker ──────────────────────────────────────────

async def run_learning_session(
    topic: str,
    llm=None,
    parent_page_id: Optional[str] = None,
    user_id: str = "local_user",
    bot_id: str = "local_bot",
) -> Dict[str, Any]:
    """
    Full autonomous learning session:
    1. LLM explains the concept
    2. LLM generates 5 exercises
    3. Creates Notion page with everything
    4. Returns summary + Notion URL
    """
    if llm is None:
        from backend.llm.universal_provider import UniversalProvider
        llm = UniversalProvider(provider="auto", mode="AUTO")

    # Step 1: Generate explanation
    explain_prompt = (
        f"Explain the concept of '{topic}' clearly and concisely in 3-4 paragraphs. "
        "Target audience: intermediate learner. Be precise and pedagogical."
    )
    try:
        explanation = await llm.complete(explain_prompt)
        if explanation.startswith("❌"):
            return {"success": False, "message": f"LLM failed to generate explanation: {explanation}"}
    except Exception as e:
        return {"success": False, "message": f"LLM error: {e}"}

    # Step 2: Generate exercises
    exercise_prompt = (
        f"Generate exactly 5 practice exercises for the topic '{topic}'. "
        "Each exercise should be on its own line, numbered 1-5. "
        "Mix difficulty: 2 easy, 2 medium, 1 challenging. "
        "Return ONLY the exercises, no extra explanation."
    )
    try:
        exercises_raw = await llm.complete(exercise_prompt)
        if exercises_raw.startswith("❌"):
            exercises = [
                f"Write a basic example of {topic}",
                f"Explain {topic} in your own words",
                f"Create a small program using {topic}",
                f"Find and fix a bug related to {topic}",
                f"Build a real-world mini-project using {topic}",
            ]
        else:
            # Parse numbered list
            import re
            lines = [re.sub(r"^\d+[\.\)]\s*", "", l).strip() for l in exercises_raw.split("\n") if l.strip()]
            exercises = [l for l in lines if len(l) > 5][:5]
            if not exercises:
                exercises = [exercises_raw]
    except Exception as e:
        exercises = [f"Practice exercise for {topic} - {i}" for i in range(1, 6)]

    # Step 3: Create Notion page
    notion_result = create_learning_tracker(
        topic=topic,
        explanation=explanation,
        exercises=exercises,
        parent_page_id=parent_page_id,
        user_id=user_id,
        bot_id=bot_id,
    )

    return {
        "success": notion_result.get("success", False),
        "topic": topic,
        "explanation": explanation,
        "exercises": exercises,
        "notion_page_url": notion_result.get("page_url"),
        "notion_page_id": notion_result.get("page_id"),
        "message": notion_result.get("message", ""),
    }
