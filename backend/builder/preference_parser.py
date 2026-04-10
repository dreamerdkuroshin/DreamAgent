"""
backend/builder/preference_parser.py

Pure-Python (zero LLM) parser for website builder preferences.
Fast, deterministic, no token cost.
"""
import re

BUILDER_TRIGGERS = [
    "build a website", "make a website", "create a website",
    "build website", "make website", "create website",
    "building a website", "building website", "making website",
    "build app", "make app", "create app",
    "build me a", "make me a", "create me a",
    "build a site", "make a site", "create a site",
    "build a store", "create a store", "build shop",
    "build landing", "create landing",
    "i want a website", "i need a website",
    "website for me", "app for me",
    "website builder", "ecommerce website"
]

# ── Product type keyword map ─────────────────────────────────────────────────
# Maps a keyword (found in user text) → canonical product label shown in UI.
ECOMMERCE_PRODUCT_KEYWORDS: dict[str, str] = {
    # Electronics
    "mobile":       "Mobile Phones",
    "mobiles":      "Mobile Phones",
    "smartphone":   "Smartphones",
    "smartphones":  "Smartphones",
    "phone":        "Phones",
    "phones":       "Phones",
    "laptop":       "Laptops",
    "laptops":      "Laptops",
    "computer":     "Computers",
    "computers":    "Computers",
    "tablet":       "Tablets",
    "tablets":      "Tablets",
    "headphone":    "Headphones",
    "headphones":   "Headphones",
    "earphone":     "Earphones",
    "earphones":    "Earphones",
    "tv":           "Televisions",
    "television":   "Televisions",
    "camera":       "Cameras",
    "cameras":      "Cameras",
    "watch":        "Watches",
    "watches":      "Watches",
    "smartwatch":   "Smartwatches",
    # Food & Beverage
    "chocolate":    "Chocolates",
    "chocolates":   "Chocolates",
    "food":         "Food & Beverage",
    "cake":         "Cakes & Bakery",
    "cakes":        "Cakes & Bakery",
    "bakery":       "Bakery Items",
    "coffee":       "Coffee & Beverages",
    "restaurant":   "Restaurant",
    # Clothing & Fashion
    "cloth":        "Clothing",
    "clothes":      "Clothing",
    "clothing":     "Clothing",
    "fashion":      "Fashion",
    "shirt":        "Shirts",
    "shirts":       "Shirts",
    "dress":        "Dresses",
    "dresses":      "Dresses",
    "shoe":         "Shoes",
    "shoes":        "Shoes",
    "sneaker":      "Sneakers",
    "sneakers":     "Sneakers",
    "bag":          "Bags",
    "bags":         "Bags",
    "jewelry":      "Jewelry",
    "jewellery":    "Jewelry",
    "accessory":    "Accessories",
    "accessories":  "Accessories",
    # Books & Media
    "book":         "Books",
    "books":        "Books",
    # Home & Lifestyle
    "furniture":    "Furniture",
    "toy":          "Toys",
    "toys":         "Toys",
    "plant":        "Plants",
    "plants":       "Plants",
    "furniture":    "Furniture",
    # Vehicles
    "car":          "Cars",
    "cars":         "Cars",
    "vehicle":      "Vehicles",
    "vehicles":     "Vehicles",
    "bike":         "Bikes",
    "bikes":        "Bikes",
    # Health & Beauty
    "supplement":   "Supplements",
    "supplements":  "Supplements",
    "cosmetic":     "Cosmetics",
    "cosmetics":    "Cosmetics",
    "skincare":     "Skincare Products",
    "medicine":     "Medicines",
    "medicines":    "Medicines",
    # Digital / SaaS
    "software":     "Software",
    "course":       "Online Courses",
    "courses":      "Online Courses",
    "subscription": "Subscriptions",
    "service":      "Services",
    "services":     "Services",
}

RECALL_TRIGGERS = [
    "build website", "build app", "build me", "create website",
    "make website", "make app",
]


def is_builder_request(text: str) -> bool:
    """Returns True if the user's message is a website/app build request."""
    t = text.lower().strip()
    if any(trigger in t for trigger in BUILDER_TRIGGERS):
        return True
    if re.search(r'\b(build|make|create|generate)\b.*\b(website|app|site|store|shop|landing|portfolio|blog)\b', t):
        return True
    return False


def is_recall_trigger(text: str) -> bool:
    """Returns True if the message should trigger PCO builder preference recall."""
    t = text.lower().strip()
    if any(trigger in t for trigger in RECALL_TRIGGERS):
        return True
    if re.search(r'\b(build|make|create|generate)\b.*\b(website|app|site|store|shop)\b', t):
        return True
    return False


def extract_product_type(text: str) -> str | None:
    """
    Scans user text for a product keyword and returns the canonical label.
    Returns None if no product is detected.
    """
    t = text.lower()
    for keyword, label in ECOMMERCE_PRODUCT_KEYWORDS.items():
        # word-boundary aware matching
        if re.search(r'\b' + re.escape(keyword) + r'\b', t):
            return label
    return None


def parse_builder_preferences(text: str) -> dict:
    """
    Extracts structured builder preferences from a natural language string.

    Example input:  "modern + sell mobiles + full app"
    Example output: {
        "design": "modern",
        "type": "ecommerce",
        "product_type": "Mobile Phones",
        "backend": True,
        "features": {"auth": False, "payment": True, "dashboard": False}
    }
    """
    text_lower = text.lower()

    # --- Design Style ---
    if "cinematic" in text_lower or "dramatic" in text_lower or "immersive" in text_lower:
        design = "cinematic"
    elif "luxury" in text_lower or "premium" in text_lower or "elegant" in text_lower:
        design = "premium"
    elif "colorful" in text_lower or "vibrant" in text_lower or "bright" in text_lower:
        design = "colorful"
    elif "minimal" in text_lower or "clean" in text_lower or "simple" in text_lower:
        design = "minimal"
    elif "modern" in text_lower or "sleek" in text_lower or "dark" in text_lower:
        design = "modern"
    else:
        design = None  # Force clarification

    # --- Site Type ---
    if any(k in text_lower for k in ["cinematic", "immersive", "parallax"]):
        site_type = "cinematic"
    elif any(k in text_lower for k in ["sell", "store", "shop", "ecommerce", "e-commerce", "product", "selling"]):
        site_type = "ecommerce"
    elif any(k in text_lower for k in ["attendance", "management system", "school", "office", "management"]):
        site_type = "management"
    elif any(k in text_lower for k in ["social media", "social network", "profile", "followers", "reels"]):
        site_type = "social"
    elif any(k in text_lower for k in ["gaming", "game hosting", "leaderboard", "cloud gaming"]):
        site_type = "gaming"
    elif any(k in text_lower for k in ["dashboard", "admin", "analytics", "panel"]):
        site_type = "dashboard"
    elif any(k in text_lower for k in ["blog", "article", "post", "news", "content website"]):
        site_type = "blog"
    elif any(k in text_lower for k in ["educational", "edtech", "course", "quiz", "udemy"]):
        site_type = "edtech"
    elif any(k in text_lower for k in ["booking", "appointment", "time slot", "calendar"]):
        site_type = "booking"
    elif any(k in text_lower for k in ["portfolio", "showcase", "projects", "resume"]):
        site_type = "portfolio"
    elif any(k in text_lower for k in ["chat", "messaging", "whatsapp"]):
        site_type = "chat"
    elif any(k in text_lower for k in ["business", "corporate", "company"]):
        site_type = "corporate"
    elif any(k in text_lower for k in ["streaming", "video player", "netflix", "youtube"]):
        site_type = "streaming"
    elif any(k in text_lower for k in ["saas", "software as a service", "online tool", "subscription"]):
        site_type = "saas"
    elif any(k in text_lower for k in ["tool", "utility website", "converter", "formatter", "pdf tools"]):
        site_type = "utility"
    elif any(k in text_lower for k in ["ai-powered", "ai website", "chatbot", "image generator", "code assistant", "ai tool"]):
        site_type = "ai"
    elif any(k in text_lower for k in ["landing", "marketing"]):
        site_type = "landing"
    elif extract_product_type(text_lower):
        site_type = "ecommerce"
    else:
        site_type = None  # Force clarification

    # --- Backend requirement ---
    has_backend_trigger = any(k in text_lower for k in [
        "full app", "full stack", "full-stack", "backend",
        "database", "api", "auth", "login", "signup",
        "users", "register", "payment", "stripe",
    ])
    needs_backend = True if has_backend_trigger else None  # None implies ask

    # --- Database requirement ---
    database = None
    if "sqlite" in text_lower:
        database = "sqlite"
    elif "mongo" in text_lower:
        database = "mongodb"
    elif "postgres" in text_lower or "psql" in text_lower:
        database = "postgresql"

    # --- Product type (what is being sold) ---
    product_type = extract_product_type(text_lower)

    # --- Feature flags ---
    features = {
        "auth": any(k in text_lower for k in ["login", "auth", "signup", "register", "users"]),
        "payment": any(k in text_lower for k in ["payment", "stripe", "sell", "buy", "checkout"]),
        "dashboard": any(k in text_lower for k in ["dashboard", "admin", "analytics"]),
    }

    result = {
        "design": design,
        "type": site_type,
        "backend": needs_backend,
        "database": database,
        "features": features,
    }
    if product_type:
        result["product_type"] = product_type
    return result

# Canonical button-option mappings for frontend UI
DESIGN_OPTIONS = ["Modern", "Cinematic", "Luxury", "Colorful", "Simple"]
TYPE_OPTIONS = ["E-commerce", "Cinematic", "Dashboard", "Blog", "Portfolio", "Landing Page"]
BACKEND_OPTIONS = ["Simple Site", "Full App"]

# ── Update intent detection ─────────────────────────────────────────────────
UPDATE_TRIGGERS = [
    "add login", "add auth", "dark mode", "light mode", "change color",
    "add hero", "add footer", "add payment", "add stripe", "make it dark",
    "change the color", "add a section", "update the", "modify the",
    "change the design", "remove the", "edit the", "fix the",
]

CONTINUE_LAST_TRIGGERS = [
    "continue last project", "continue my project", "continue my last",
    "resume last build", "resume my project",
    "open last project", "go back to my project", "last build", "previous build",
    "continue where", "pick up where", "retry previous task", "retry previous",
    "retry task", "retry", "previous task",
]


def is_update_request(text: str, session_id: str = "") -> bool:
    """Returns True if the message looks like a re-edit request on an existing build."""
    t = text.lower()
    return bool(session_id) and any(trigger in t for trigger in UPDATE_TRIGGERS)


def is_continue_last(text: str) -> bool:
    """Returns True if user wants to resume/continue their last project."""
    t = text.lower()
    return any(trigger in t for trigger in CONTINUE_LAST_TRIGGERS)


# ── Confidence scoring ──────────────────────────────────────────────────────
HIGH_CONFIDENCE_KEYWORDS = [
    "modern", "luxury", "colorful", "simple",
    "e-commerce", "ecommerce", "sell", "store", "shop",
    "dashboard", "admin", "blog", "portfolio", "landing",
    "management", "social", "gaming", "edtech", "booking",
    "chat", "corporate", "streaming", "saas", "utility", "ai",
    "full app", "full stack", "backend", "login", "auth",
]


def _keyword_confidence(text: str) -> float:
    """Returns 0.0–1.0 confidence that we can parse prefs from keyword matching alone."""
    t = text.lower()
    hits = sum(1 for k in HIGH_CONFIDENCE_KEYWORDS if k in t)
    return min(hits / 2.0, 1.0)


async def smart_parse_preferences(text: str, provider: str = "auto", model: str = "") -> dict:
    """
    Hybrid parser:
    - High-confidence keyword match → fast parse (0 LLM calls)
    - Low-confidence → LLM interprets the intent then merges with keyword parse

    Example low-confidence input:  "something like Amazon"
    Example LLM clarification output: {"type": "ecommerce", "design": "modern", "backend": true}
    """
    t_lower = text.lower()
    
    # ── Priority 0: Product type correction ("no product type mobiles", "change product to phones") ──
    # Must check BEFORE the generic "no" rejection gate so we can handle it gracefully.
    _product_update_patterns = [
        r'(?:no|change|update|set)\s+product\s+(?:type\s+)?(?:to\s+|is\s+)?(\w+)',
        r'product\s+(?:type\s+)?(?:is\s+|=\s*)?(\w+)',
        r'(?:i\s+(?:sell|want\s+to\s+sell))\s+(\w+)',
        r'(?:selling|for\s+selling)\s+(\w+)',
    ]
    for _pat in _product_update_patterns:
        _m = re.search(_pat, t_lower)
        if _m:
            _candidate = _m.group(1).strip()
            # Check if it maps to a known product
            _detected = None
            for _kw, _label in ECOMMERCE_PRODUCT_KEYWORDS.items():
                if re.search(r'\b' + re.escape(_kw) + r'\b', _candidate):
                    _detected = _label
                    break
            # Also try the full remaining text in case it's multi-word
            if not _detected:
                _detected = extract_product_type(t_lower)
            if _detected:
                return {"_product_update": True, "product_type": _detected, "type": "ecommerce"}

    # State: User explicitly confirmed (build it)
    CONFIRM_WORDS = {"yes", "ok", "confirm", "go", "start", "done"}
    # Use split() to prevent substring matches (e.g. 'go' inside 'good')
    if any(word in t_lower.split() for word in CONFIRM_WORDS) or any(w in t_lower for w in ["use this", "build it", "proceed", "looks good", "do it", "go ahead"]):
        return {"_confirmation": True}

    # State: User rejected / wants to edit — explicit state machine branch
    # Guard: only trigger if there's no new product info embedded in the message.
    _has_new_product = bool(extract_product_type(t_lower))
    _has_rejection_word = any(w in t_lower for w in ["no", "change", "edit", "different", "not that", "actually", "wait", "modify"])
    if _has_rejection_word and not _has_new_product:
        return {"_rejection": True}
        
    # State: Ambiguous response ("maybe", "not sure", "possibly")
    if any(w in t_lower for w in ["maybe", "not sure", "possibly", "idk", "i don't know", "decide for me"]):
        return {"_ambiguous": True}
        
    confidence = _keyword_confidence(text)

    if confidence >= 0.5:
        return parse_builder_preferences(text)

    # LLM fallback for ambiguous input
    try:
        from backend.llm.universal_provider import UniversalProvider
        llm = UniversalProvider(provider=provider, model=model)
        prompt = f"""A user wants to build a website/app. They said: "{text}"

Extract their preferences and return ONLY a JSON object:
{{"design": "modern"|"luxury"|"colorful"|"simple"|null, "type": "ecommerce"|"dashboard"|"landing"|"blog"|"portfolio"|null, "backend": true|false|null}}

CRITICAL RULE:
ONLY return fields the user EXPLICITLY wants to change. If they do not mention a field, it MUST be null. (This prevents partial overwriting of good data).
No explanation, no markdown."""
        result = llm.generate([{"role": "user", "content": prompt}])
        result = result.strip().strip("```json").strip("```").strip()
        import json
        parsed_llm = json.loads(result)
        # Merge: LLM provides type/design, keyword parse fills features
        kw = parse_builder_preferences(text)
        kw["design"] = parsed_llm.get("design", kw["design"])
        kw["type"] = parsed_llm.get("type", kw["type"])
        kw["backend"] = parsed_llm.get("backend", kw["backend"])
        return kw
    except Exception:
        # If LLM fails, fallback to keyword parse regardless
        return parse_builder_preferences(text)

def build_prefs_summary(prefs: dict) -> str:
    """
    Returns a human-readable markdown summary of current preferences.
    """
    d = (prefs.get('design') or 'Not set').title()
    t = (prefs.get('type') or 'Not set').title()
    b = "Full App" if prefs.get('backend') is True else ("Simple Site" if prefs.get('backend') is False else "Not set")
    pt = prefs.get('product_type', '')
    product_line = f"• **Selling:** {pt}\n" if pt else ""
    return (
        f"• **Design:** {d}\n"
        f"• **Type:** {t}\n"
        f"{product_line}"
        f"• **Backend:** {b}"
    )


def finalize_preferences(prefs: dict) -> dict:
    """
    Production-grade preference finalizer.
    Auto-defaults database when backend is enabled, clears it when not.
    Call this BEFORE check_missing_preferences.
    """
    if prefs.get("backend") and not prefs.get("database"):
        prefs["database"] = "sqlite"

    if not prefs.get("backend"):
        prefs["database"] = None

    return prefs


REQUIRED = ["type", "design", "database"]

def check_missing_preferences(prefs: dict) -> str:
    """
    Checks if preferences are fully formed or if clarification is needed.
    Follows a STRICT state machine:
    ask_type -> ask_design -> ask_database -> confirm -> execute
    """
    # Auto-finalize database before checking
    prefs = finalize_preferences(prefs)

    missing = [k for k in REQUIRED if not prefs.get(k)]
    
    if not missing:
        return ""

    if "type" in missing:
        return (
            "Let's set up your website 🔧\n\n"
            "**What type of website do you want?**\n\n"
            "[🔘 E-commerce](action:ecommerce) [🔘 Cinematic](action:cinematic) [🔘 Dashboard](action:dashboard) [🔘 Portfolio](action:portfolio) [🔘 Landing Page](action:landing)"
        )
    elif "design" in missing:
        return (
            f"**Type:** ✅ {prefs.get('type', '').title()}\n\n"
            "**Choose your design style:**\n\n"
            "[🔘 Modern](action:modern) [🔘 Cinematic](action:cinematic) [🔘 Minimal](action:minimal) [🔘 Premium](action:premium)"
        )
    elif "database" in missing:
        return (
            f"**Design:** ✅ {prefs.get('design', '').title()}\n\n"
            "**Do you need a full backend database?**\n\n"
            "[🔘 Yes, use SQLite](action:use sqlite) [🔘 Yes, use PostgreSQL](action:use postgresql)\n"
            "[🔘 Yes, use MongoDB](action:use mongodb) [🔘 No, static only](action:simple site)"
        )
        
    return ""

def get_rejection_response(prefs: dict) -> str:
    """
    Called when user says 'no' or wants to change the build preferences.
    """
    design = prefs.get('design', 'not set') or 'not set'
    app_type = prefs.get('type', 'not set') or 'not set'
    backend = prefs.get('backend')
    backend_str = "Full app" if backend is True else ("Static site" if backend is False else "not set")
    db_str = prefs.get('database', 'not set') or 'not set'
    pt = prefs.get('product_type', '')
    product_line = f"• Selling → **{pt}**\n" if pt else ""
    
    return (
        f"Got it 👍 Let's edit your plan.\n\n"
        f"Current plan:\n"
        f"• Design → **{design}**\n"
        f"• App Type → **{app_type}**\n"
        f"{product_line}"
        f"• Backend → **{backend_str}**\n"
        f"• Database → **{db_str}**\n\n"
        f"Quick actions:\n"
        f"[🔘 Change Design](action:change design) [🔘 Change Product](action:change product) [🔘 Change Database](action:change database)\n\n"
        f"Or just tell me what to change.\n\n"
        f"[🔘 Build it now](action:yes)"
    )
