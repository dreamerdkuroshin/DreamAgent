import re
import random

CHAT_KEYWORDS = ["bro", "wtf", "lol", "lmao", "yo", "what's up", "sup", "damn", "hey", "chill",
                 "funny", "joke", "hi", "hello", "grok", "bruh", "ngl", "fr", "imo", "tbh", "smh", "gg", "wdym"]

# Only TRULY complex tasks go to UltraAgent
TASK_KEYWORDS = ["error", "fix", "bug", "stack trace", "debug", "deploy", "build", "refactor",
                 "implement", "generate code", "analyze", "compare", "difference between",
                 "function", "class", "import", "install", "setup", "configure", "solve",
                 "calculate", "convert", "translate", "write a", "create a", "make a",
                 "build me", "code me", "show me how to", "step by step"]

# Simple factual → direct LLM (no agent loop)
SIMPLE_FACT_PREFIXES = ["what is", "what are", "what was", "what were", "what does",
                        "who is", "who was", "who are", "where is", "where was",
                        "when did", "when was", "why is", "why does", "why did",
                        "how does", "how did", "how is", "define ", "explain what",
                        "tell me about", "describe ", "give me info", "what's the difference",
                        "list the", "name the", "can you explain"]

# ⚡ INSTANT: single-word / pure casual — templates only, zero LLM
INSTANT_EXACT = {"wtf", "lol", "lmao", "lmfao", "yo", "sup", "hey", "hi", "hello",
                 "haha", "hahaha", "ok", "okay", "k", "kk", "cool", "nice", "bruh",
                 "bro", "ngl", "fr", "gg", "smh", "thx", "ty", "thanks", "bye",
                 "byeee", "wyd", "wdym", "wbu", "hbu", "ikr", "ik", "nah",
                 "yep", "yup", "nope", "aight", "bet"}

INSTANT_PREFIXES = ["what u ", "what r u ", "what are u ", "what you ", "wyd", "u there",
                    "you there", "r u ", "are u ", "u up", "you up", "what's good",
                    "whats good", "what's popping", "whats popping", "sup bro", "hey bro",
                    "yo bro", "you okay", "u ok", "you good", "u good",
                    "how r u", "how are u", "how u doing", "how you doing"]


# ⚡ LITE FAST: Short casual chat or quick factual lookup (<1s direct LLM)
LITE_FACT_PREFIXES = [
    "what is", "what are", "what was", "what were", "what does",
    "who is", "who was", "who are", "where is", "where was",
    "when did", "when was", "why is", "why does", "why did",
    "how does", "how did", "how is", "define ", "explain what",
    "tell me about", "describe ", "give me info", "what's the difference",
    "list the", "name the", "can you explain",
]
LITE_CHAT_KEYWORDS = [
    "bro", "wtf", "lol", "lmao", "yo", "what's up", "sup", "damn",
    "hey", "chill", "funny", "joke", "haha", "grok", "bruh", "ngl",
    "fr", "imo", "tbh", "smh", "gg", "wdym",
]

# 🧠 STANDARD: Single structured LLM call — coding help, writing, refactoring
STANDARD_KEYWORDS = [
    "solve", "explain", "refactor", "write", "create", "make",
    "convert", "translate", "summarize", "summary", "rewrite",
    "improve", "review", "format", "generate", "draft", "outline",
    "how to make", "how to write", "how to build", "how to create",
    "give me a", "show me", "write me", "make me", "help me",
    "api code", "backend", "fastapi", "snippet", "example",
    "step by step", "in python", "in javascript", "in typescript",
    "dsa", "algorithm", "data structure", "problem", "solution",
]

# 🚀 ULTRA: Multi-step planner + tools, long documents, full systems
ULTRA_KEYWORDS = [
    "build", "develop", "deploy", "setup", "configure", "install",
    "implement full", "full system", "production", "scalable",
    "end to end", "end-to-end", "from scratch", "full stack",
    "build me a", "build a full", "create a full", "make a full",
    "debug", "bug", "error", "fix", "stack trace", "traceback",
    "inspect", "investigate", "research", "latest", "recent",
    "find sources", "with sources", "compare models", "compare providers",
    "read this file", "analyze this", "analyze the", "process this",
    "summarize 50", "summarize this document", "this pdf",
    "document", "contract", "transcript", "notes",
    "agent", "workflow", "automate", "pipeline", "schedule",
    "run a", "execute", "host", "fine-tune",
]

def _compile_regex(kw_list):
    """Pre-compiles exact word boundary regex for a list of tokens."""
    pattern = r'(?<!\w)(?:' + '|'.join(re.escape(k) for k in kw_list) + r')(?!\w)'
    return re.compile(pattern)

RE_ULTRA = _compile_regex(ULTRA_KEYWORDS)
RE_STANDARD = _compile_regex(STANDARD_KEYWORDS)
RE_INSTANT = _compile_regex(list(INSTANT_EXACT))
RE_LITE_CHAT = _compile_regex(LITE_CHAT_KEYWORDS)
RE_FIX_BUGS = _compile_regex(["fix", "error", "bug"])
RE_SUMMARIZE = _compile_regex(["summarize"])

def classify_speed(text: str) -> str:
    t = text.strip().lower().rstrip("?!.")
    words = t.split()
    word_count = len(words)

    # ── ⚡ INSTANT: single casual tokens → pure template, 0ms ──────────────
    if t in INSTANT_EXACT:
        return "instant"
    if word_count <= 5:
        if any(t.startswith(prefix) for prefix in INSTANT_PREFIXES):
            return "instant"
        if RE_INSTANT.search(t) and not (RE_ULTRA.search(t) or RE_STANDARD.search(t)):
            return "instant"

    # ── 🚀 ULTRA: detect first — strong signal words override everything ──
    if RE_ULTRA.search(t):
        # Short queries with incidental ULTRA words → don't go full pipeline
        if word_count <= 6 and RE_FIX_BUGS.search(t):
            return "simple"
        if word_count <= 4 and RE_SUMMARIZE.search(t):
            return "fast"
        # Guard: very short queries (<=5 words) should never go full even
        # if they happen to contain an ULTRA keyword like 'latest' or 'build'
        if word_count <= 5:
            return "fast"
        return "full"

    # ── 🧠 STANDARD: single structured LLM call ───────────────────────────
    if RE_STANDARD.search(t):
        return "simple"

    # ── ⚡ LITE FAST: simple factual / casual chat ─────────────────────────
    if any(t.startswith(p) for p in LITE_FACT_PREFIXES):
        return "fast"
    if RE_LITE_CHAT.search(t):
        return "fast"

    # ── Length-based fallback ─────────────────────────────────────────────
    if word_count > 30:
        return "full"
    if word_count > 12:
        return "simple"
    return "fast"


def detect_mode(text: str) -> str:
    speed = classify_speed(text)
    if speed in ("full",):
        return "TASK"
    if speed == "instant":
        return "CHAT"
    t = text.lower()
    if any(k in t for k in TASK_KEYWORDS):
        return "TASK"
    return "CHAT"


def get_persona_prompt(text: str, is_autonomous: bool = False) -> str:
    if is_autonomous:
        return (
            "You are DreamAgent in AUTONOMOUS MODE.\n"
            "- Break tasks into concise steps and execute tool calls efficiently.\n"
            "- Think strictly like an AI agent, not a chatbot.\n"
        )

    mode = detect_mode(text)

    if mode == "TASK":
        return (
            "You are DreamAgent in TASK MODE (serious, accurate, structured).\n"
            "- Use structured, clear, technical responses.\n"
            "- Focus on accuracy, steps, and detailed explanations.\n"
            "- No slang or profanity unless strictly relevant to the query.\n"
            "- Maintain professional clarity.\n"
        )
    else:
        tones = ["chill 😎", "sarcastic 💀", "hype 🚀", "calm 🧠"]
        selected_tone = random.choice(tones)
        t = text.lower()
        if "chill" in t: selected_tone = "chill 😎"
        elif "sarcastic" in t or "roast" in t: selected_tone = "sarcastic 💀"
        elif "hype" in t or "excited" in t: selected_tone = "hype 🚀"
        elif "calm" in t: selected_tone = "calm 🧠"

        return (
            f"You are DreamAgent in CHAT MODE (Mood: {selected_tone}).\n"
            "- Be natural, casual, human-like. Match user energy.\n"
            "- You can use slang, humor, sarcasm (like Grok / Twitter style).\n"
            "- You can use mild profanity when appropriate (e.g., 'damn', 'bro', 'wtf', 'lol').\n"
            "- DO NOT be offensive, hateful, or toxic. Never lecture about language.\n"
            "- Respond like a real online friend, not a formal assistant.\n"
            "- Keep responses SHORT and punchy (1–3 sentences max for casual chat).\n"
        )
