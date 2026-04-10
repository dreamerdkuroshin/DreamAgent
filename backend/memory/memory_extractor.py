"""
backend/memory/memory_extractor.py

Pro-level memory extraction using an LLM.
Implements cheap pre-filters, normalized scoring, and category expansion.
"""
import json
import logging
from dataclasses import dataclass
from backend.llm.selector import get_llm

logger = logging.getLogger(__name__)

# Expanded Memory Categories
VALID_CATEGORIES = [
    "identity",
    "style",
    "preference",
    "dislike",
    "project",
    "skill",
    "tool_usage",
    "goal_short",
    "goal_long",
    "conversation_summary",
    "fact",
    "general"
]

@dataclass
class MemoryExtraction:
    store: bool
    content: str
    category: str
    importance: float
    confidence: float

# Cheap Pre-filter Keywords
SIGNAL_WORDS = {
    "my name", "i am", "i like", "i love", "i hate", "prefer", "want to", "need to",
    "working on", "building", "using", "know how", "remember", "never", "always"
}

def should_extract(message: str) -> bool:
    """Cheap pre-filter to protect the LLM from processing trivial messages."""
    t = message.lower()
    
    if len(t) < 15:
        return False
        
    return any(word in t for word in SIGNAL_WORDS) or len(t) > 100

def _normalize_extraction(parsed: dict) -> MemoryExtraction:
    """Validates and normalizes LLM extraction fields."""
    store = bool(parsed.get("store", False))
    content = str(parsed.get("content", "")).strip()
    category = str(parsed.get("category", "general")).lower()
    
    if category not in VALID_CATEGORIES:
        category = "general"
        
    # Clamp importance scores to prevent LLM hallucination extremes
    try:
        importance = float(parsed.get("importance", 0.5))
    except (ValueError, TypeError):
        importance = 0.5
        
    try:
        confidence = float(parsed.get("confidence", 1.0))
    except (ValueError, TypeError):
        confidence = 1.0
        
    importance = max(0.3, min(importance, 0.95))
    confidence = max(0.0, min(confidence, 1.0))
    
    # Strict floor rules for critical definitions
    if category in ["identity", "fact"]:
        importance = max(importance, 0.8)
        
    return MemoryExtraction(
        store=store and bool(content),
        content=content,
        category=category,
        importance=importance,
        confidence=confidence
    )


async def extract_memory(message: str) -> MemoryExtraction:
    """Uses LLM to extract structured memory facts from a user message."""
    if not should_extract(message):
        return MemoryExtraction(store=False, content="", category="general", importance=0.0, confidence=0.0)
        
    prompt = f"""Analyze this message and extract memory if it contains important, lasting information about the user.

Message: "{message}"

Valid categories: {json.dumps(VALID_CATEGORIES)}

Return ONLY a JSON object:
{{
  "store": true/false,
  "content": "the clean, standalone fact to remember (3rd person)",
  "category": "one of the valid categories",
  "importance": 0.3 to 0.95,
  "confidence": 0.0 to 1.0
}}

Rules:
- "My name is Manthan" -> store, identity, imp: 0.95, conf: 1.0
- "I hate verbose explanations" -> store, style (or dislike), imp: 0.8, conf: 0.9
- "My goal is to launch by April" -> store, goal_short, imp: 0.8, conf: 0.9
- "I want to eventually build a startup" -> store, goal_long, imp: 0.8, conf: 0.9
- "I might switch to Node.js" -> store, preference, imp: 0.6, conf: 0.4
- "I enjoy coding in Python" -> store, preference, imp: 0.7, conf: 0.9
- "I'm building an AI agent" -> store, project, imp: 0.75, conf: 1.0
- "What's the weather?" -> do NOT store
- "Thanks!", "ok", "yes" -> do NOT store
- Questions about facts, current events -> do NOT store
- Only store PERSISTENT and PERSONAL information.

Examples:
Input: "I hate raw CSS, I always use Tailwind"
Output: {{"store": true, "content": "User prefers Tailwind CSS over standard CSS.", "category": "preference", "importance": 0.8, "confidence": 1.0}}

Input: "I'm maybe thinking about trying out React"
Output: {{"store": true, "content": "User is considering trying React.", "category": "preference", "importance": 0.6, "confidence": 0.4}}

Input: "What time is it in Tokyo?"
Output: {{"store": false, "content": "", "category": "general", "importance": 0.0, "confidence": 0.0}}

Return ONLY JSON, no explanation.
"""

    llm = get_llm("auto")
    try:
        if hasattr(llm, "get_chat_completion"):
            result_str = await llm.get_chat_completion(prompt)
        elif hasattr(llm, "generate"):
            # Fallback to sync generator if async is not correctly rigged
            result_str = llm.generate([{"role": "user", "content": prompt}])
        else:
            return MemoryExtraction(store=False, content="", category="general", importance=0.0, confidence=0.0)
            
        result_str = result_str.strip()
        if result_str.startswith("```json"):
            result_str = result_str[7:-3]
        elif result_str.startswith("```"):
            result_str = result_str[3:-3]
            
        result_str = result_str.strip()
        parsed = json.loads(result_str)
        
        return _normalize_extraction(parsed)
        
    except Exception as e:
        logger.warning(f"[MemoryExtractor] Extraction failed: {e}")
        return MemoryExtraction(store=False, content="", category="general", importance=0.0, confidence=0.0)
