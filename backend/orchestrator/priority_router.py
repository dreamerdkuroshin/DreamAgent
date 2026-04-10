"""
backend/orchestrator/priority_router.py

THE single source of truth for intent detection in DreamAgent.

ALL routing decisions MUST flow through detect_intent() here.
Never use _fast_classify(), keyword_router detect_intents(), or
any other ad-hoc keyword matching outside this module.

Priority order (top = highest priority, overrides everything below):
  1. news        — "news", "latest", "today", "update", "war", "breaking"
  2. finance     — "price", "bitcoin", "stock", "market"
  3. weather     — "weather", "temperature", "rain", "forecast"
  4. search      — "search", "google", "find", "look up"
  5. builder     — "build", "create website", "make app", "make website"
  6. coding      — "code", "python", "program", "script", "function"
  7. autonomous  — "automate", "loop", "do this task"
  8. chat        — default fallback
"""
from __future__ import annotations

import re
import logging
from typing import Optional
from langdetect import detect

logger = logging.getLogger(__name__)

def normalize_query(q: str):
    """Detects lang and lowercases."""
    try:
        lang = detect(q)
    except:
        lang = "en"
    return q.lower(), lang


# ── Intent keyword banks (ordered sets) ─────────────────────────────────────

_NEWS_WORDS = {
    # English
    "news", "latest", "today", "update", "updates", "war", "breaking",
    "headlines", "current events", "what happened", "recent", "trending",
    "happening", "crisis", "conflict", "incident", "report", "announce",
    "election", "attack", "disaster", "emergency",
    # Hindi
    "खबर", "समाचार", "ताज़ा", "आज की खबर", "अपडेट", "ब्रेकिंग",
    # Chinese
    "新闻", "最新", "报道",
    # Japanese
    "ニュース", "最新", "報道",
    # Korean
    "뉴스", "최신", "보도",
    # European
    "noticias", "actualizado", "nouvelles", "nachrichten", "notizie"
    # Arabic
    "أخبار", "آخر الأخبار", "اليوم", "تحديث", "عاجل", "أخبار عاجلة",
    "أخبار اليوم", "آخر الأخبار اليوم", "أخبار عاجلة اليوم",
    "أخبار العالم", "أخبار العالم اليوم", "أخبار العالم عاجلة",
    "أخبار العالم عاجلة اليوم", "أخبار العالم عاجلة اليوم",
}

_FINANCE_WORDS = {
    "price", "bitcoin", "stock", "market", "crypto", "nifty", "sensex",
    "nasdaq", "dow jones", "usd", "inr", "rupee", "dollar", "gold",
    "investment", "portfolio", "trading", "forex",
}

_WEATHER_WORDS = {
    "weather", "temperature", "rain", "forecast", "humid", "wind",
    "storm", "snow", "sunny", "celsius", "fahrenheit",
}

_SEARCH_WORDS = {
    "search", "google", "find", "look up", "lookup", "search the web",
    "search for", "who is", "what is",
}

# Builder: requires at least one of these PLUS a product noun
_BUILDER_PHRASES = [
    "build", "create website", "create web", "make website", "make app",
    "make a website", "make an app", "create app", "create a website",
    "create a web app", "create a landing", "create a portfolio",
    "generate website", "generate app", "build me a", "build a website",
    "build an app", "build a web", "build a landing", "build a portfolio",
    "develop a website", "develop an app",
]

_CODING_WORDS = {
    "code", "python", "program", "script", "function", "class", "algorithm",
    "javascript", "typescript", "rust", "golang", "java", "c++", "sql",
    "api", "backend", "frontend", "implement", "snippet", "debug", "fix bug",
    "write a", "write me a",
}

_AUTONOMOUS_WORDS = {
    "automate", "loop", "do this task", "run this task", "repeat",
    "schedule", "every hour", "every day", "background task",
}

_CHAT_ONLY = {
    "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "bye",
    "good morning", "good night", "what's up", "how are you",
    "who are you", "what can you do",
}


def detect_intent(query: str) -> str:
    """
    THE single source of truth for intent detection.

    Returns one of:
        "news" | "finance" | "weather" | "search" | "builder" |
        "coding" | "autonomous" | "chat"

    Priority is hard-locked: news ALWAYS wins if news keywords present.
    """
    q, lang = normalize_query(query)
    words = set(re.split(r"[\s,;]+", q))  # word-tokenize

    # ── SMART ROUTER LAYER ─────────────────────────────────────────────────
    # Prioritize 'finance' so words like 'today' in 'bitcoin today' don't hit news fallback
    if words & _FINANCE_WORDS:
        logger.debug("[PriorityRouter] intent=finance")
        return "finance"

    if words & _NEWS_WORDS or any(phrase in q for phrase in [
        "news about", "give me news", "tell me news",
        "what's happening", "what is happening", "latest on",
        "latest about", "news on", "news today",
    ]):
        logger.debug("[PriorityRouter] intent=news")
        return "news"

    # ── PRIORITY 3: WEATHER ─────────────────────────────────────────────────
    if words & _WEATHER_WORDS:
        logger.debug("[PriorityRouter] intent=weather")
        return "weather"

    # ── PRIORITY 4: EXPLICIT SEARCH ─────────────────────────────────────────
    if words & _SEARCH_WORDS:
        logger.debug("[PriorityRouter] intent=search")
        return "search"

    # ── PRIORITY 5: BUILDER ─────────────────────────────────────────────────
    if any(phrase in q for phrase in _BUILDER_PHRASES):
        logger.debug("[PriorityRouter] intent=builder")
        return "builder"

    # ── PRIORITY 6: CODING ──────────────────────────────────────────────────
    if words & _CODING_WORDS:
        # Guard: don't steal "give me news" etc. — already handled above
        logger.debug("[PriorityRouter] intent=coding")
        return "coding"

    # ── PRIORITY 7: AUTONOMOUS ──────────────────────────────────────────────
    if any(kw in q for kw in _AUTONOMOUS_WORDS):
        logger.debug("[PriorityRouter] intent=autonomous")
        return "autonomous"

    # ── PRIORITY 8: CHAT ONLY (short greetings) ─────────────────────────────
    if len(q.split()) <= 6 and words & _CHAT_ONLY:
        logger.debug("[PriorityRouter] intent=chat (greeting)")
        return "chat"

    # ── DEFAULT ─────────────────────────────────────────────────────────────
    logger.debug("[PriorityRouter] intent=unknown (default)")
    return "unknown"


def detect_intent_with_confidence(query: str) -> tuple[str, float]:
    """
    Returns (intent, confidence) for logging/metrics.
    High-signal intents get 0.95, default chat gets 0.50.
    """
    intent = detect_intent(query)
    confidence_map = {
        "news": 0.90,
        "finance": 0.92,
        "weather": 0.92,
        "search": 0.88,
        "builder": 0.92,
        "coding": 0.85,
        "autonomous": 0.80,
        "chat": 0.50,
        "unknown": 0.10,
    }
    return intent, confidence_map.get(intent, 0.50)
