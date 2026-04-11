"""
backend/api/key_injector.py
===========================
Chat-driven API key injection and Google OAuth JSON file analyser.

Features:
1. Detect "my stripe key is sk_live_xxx" → store to .env + os.environ + DB instantly
2. Detect Google service-account / OAuth JSON uploads → analyse which scopes/APIs
   are enabled → if Gmail scope is present, auto-connect Gmail connector
3. Returns a structured result with discovered keys and actions taken
"""

import re
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

ENV_FILE = Path(__file__).parent.parent.parent / ".env"

# ─────────────────────────────────────────────────────────────────────────────
# KEY PATTERNS map:  (env_var_name, label, regex_pattern)
# ─────────────────────────────────────────────────────────────────────────────
_KEY_PATTERNS: List[Tuple[str, str, str]] = [
    # Stripe
    ("STRIPE_API_KEY",          "Stripe Secret Key",    r'\bsk_(?:live|test)_[A-Za-z0-9]{24,}\b'),
    ("STRIPE_PUBLISHABLE_KEY",  "Stripe Publishable",   r'\bpk_(?:live|test)_[A-Za-z0-9]{24,}\b'),
    # OpenAI
    ("OPENAI_API_KEY",          "OpenAI",               r'\bsk-(?:proj-)?[A-Za-z0-9\-_]{40,}\b'),
    # Anthropic
    ("CLAUDE_API_KEY",          "Anthropic/Claude",     r'\bsk-ant-[A-Za-z0-9\-_]{40,}\b'),
    # Tavily
    ("TAVILY_API_KEY",          "Tavily",               r'\btvly-[A-Za-z0-9\-_]{30,}\b'),
    # Ahrefs
    ("AHREFS_API_KEY",          "Ahrefs",               r'\b[A-Za-z0-9]{32,64}\b'),   # loose — only matched when "ahrefs" mentioned
    # Supabase anon
    ("SUPABASE_ANON_KEY",       "Supabase Anon Key",    r'\bsb_publishable_[A-Za-z0-9_\-]{20,}\b'),
    # Supabase service role
    ("SUPABASE_SERVICE_KEY",    "Supabase Service Key", r'\beyJ[A-Za-z0-9\-_]{50,}\.[A-Za-z0-9\-_]{50,}\.[A-Za-z0-9\-_]{30,}\b'),
    # Gemini
    ("GEMINI_API_KEY",          "Google Gemini",        r'\bAIza[A-Za-z0-9\-_]{35,}\b'),
    # Groq
    ("GROQ_API_KEY",            "Groq",                 r'\bgsk_[A-Za-z0-9]{50,}\b'),
    # Hugging Face
    ("HUGGINGFACE_API_KEY",     "HuggingFace",          r'\bhf_[A-Za-z0-9]{34,}\b'),
    # Resend
    ("RESEND_API_KEY",          "Resend",               r'\bre_[A-Za-z0-9_\-]{20,}\b'),
    # Telegram
    ("TELEGRAM_BOT_TOKEN",      "Telegram Bot Token",   r'\b[0-9]{8,10}:[a-zA-Z0-9_\-]{35,}\b'),
    # Microsoft OAuth
    ("MICROSOFT_CLIENT_ID",     "Microsoft Client ID",  r'\b[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\b'), # UUID
    ("MICROSOFT_CLIENT_SECRET", "Microsoft Client Secret", r'\b[A-Za-z0-9_\-~]{32,45}\b'),
    # Slack OAuth
    ("SLACK_CLIENT_ID",         "Slack Client ID",      r'\b\d+\.\d+\b'),
    ("SLACK_CLIENT_SECRET",     "Slack Client Secret",  r'\b[a-f0-9]{32}\b'),
    # Notion OAuth
    ("NOTION_CLIENT_ID",        "Notion Client ID",     r'\b[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\b'), # UUID
    ("NOTION_CLIENT_SECRET",    "Notion Client Secret", r'\bsecret_[a-zA-Z0-9]{30,60}\b'),
]

# Keyword hints used for context-aware detection of ambiguous keys (like Ahrefs or UUIDs)
# Keyword hints used for context-aware detection of ambiguous keys (like Ahrefs or UUIDs)
_KEYWORD_HINTS: Dict[str, List[str]] = {
    "AHREFS_API_KEY": ["ahrefs", "ahrefs key", "ahrefs api"],
    "SUPABASE_URL":   ["supabase url", "supabase project url"],
    "MICROSOFT_CLIENT_ID": ["microsoft", "azure", "teams", "excel"],
    "MICROSOFT_CLIENT_SECRET": ["microsoft", "azure", "teams", "excel"],
    "NOTION_CLIENT_ID": ["notion"],
    "NOTION_CLIENT_SECRET": ["notion"],
    "SLACK_CLIENT_ID": ["slack"],
    "SLACK_CLIENT_SECRET": ["slack"],
}


def _update_env_file(key: str, value: str) -> None:
    """Write/update a KEY=value line in the .env file."""
    if not ENV_FILE.exists():
        ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
        return
    content = ENV_FILE.read_text(encoding="utf-8")
    pattern = rf"^({re.escape(key)}=).*$"
    new_line = f"{key}={value}"
    if re.search(pattern, content, flags=re.MULTILINE):
        content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
    else:
        if not content.endswith("\n"):
            content += "\n"
        content += f"{new_line}\n"
    ENV_FILE.write_text(content, encoding="utf-8")


def _persist_key(env_var: str, value: str) -> None:
    """Store key in os.environ + .env file + optionally DB."""
    os.environ[env_var] = value
    try:
        _update_env_file(env_var, value)
    except Exception as e:
        logger.warning(f"[KeyInjector] .env write failed for {env_var}: {e}")

    # Optional DB persistence via settings service
    try:
        from backend.core.database import SessionLocal
        from backend.services import auth_service
        with SessionLocal() as db:
            auth_service.save_api_key(db, env_var, value)
    except Exception as e:
        logger.debug(f"[KeyInjector] DB persist skipped for {env_var}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. DETECT API KEYS IN CHAT MESSAGES
# ─────────────────────────────────────────────────────────────────────────────

def detect_and_store_keys(message: str) -> Dict[str, Any]:
    """
    Scan a chat message for API key patterns. For each found key:
      - Store it to os.environ
      - Persist to .env
      - Persist to DB
      - Reload relevant integration singleton

    Returns:
        {
          "found": [{"env_var": "STRIPE_API_KEY", "label": "Stripe", "preview": "sk_live_ab••••cd"}],
          "reply": "I've saved your Stripe key. You can now use Stripe payments.",
          "actions": ["reload:stripe"]
        }
    """
    msg_lower = message.lower()
    found = []
    actions = []

    for env_var, label, pattern in _KEY_PATTERNS:
        # Ahrefs key pattern and OAuth properties are loose — only fire if hinted
        if env_var in ("AHREFS_API_KEY", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET", "NOTION_CLIENT_ID", "NOTION_CLIENT_SECRET", "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"):
            hints = _KEYWORD_HINTS.get(env_var, [])
            if not any(h in msg_lower for h in hints):
                continue

        matches = re.findall(pattern, message)
        if not matches:
            continue

        value = matches[0].strip()
        if len(value) < 10:
            continue

        # Don't overwrite an already set key with an identical value
        existing = os.environ.get(env_var, "")
        if existing == value:
            found.append({
                "env_var": env_var,
                "label": label,
                "preview": _mask(value),
                "already_set": True,
            })
            continue

        _persist_key(env_var, value)
        _reload_singleton(env_var)
        verification_msg = _verify_key(env_var)

        found.append({
            "env_var": env_var,
            "label": label,
            "preview": _mask(value),
            "already_set": False,
            "verification": verification_msg
        })
        actions.append(f"saved:{env_var}")
        logger.info(f"[KeyInjector] Stored {env_var} from chat message")

    # Also handle "supabase url is https://..." pattern
    url_match = re.search(r'https://[a-z0-9]+\.supabase\.co', message, re.IGNORECASE)
    if url_match:
        url_val = url_match.group(0).strip()
        existing = os.environ.get("SUPABASE_URL", "")
        if existing != url_val:
            _persist_key("SUPABASE_URL", url_val)
            _reload_singleton("SUPABASE_URL")
            verification_msg = _verify_key("SUPABASE_URL")
            found.append({"env_var": "SUPABASE_URL", "label": "Supabase URL", "preview": url_val, "already_set": False, "verification": verification_msg})
            actions.append("saved:SUPABASE_URL")

    if not found:
        return {"found": [], "reply": None, "actions": []}

    new_keys = [f for f in found if not f.get("already_set")]
    already = [f for f in found if f.get("already_set")]

    lines = []
    if new_keys:
        lines.append("I found and saved the following API key(s):\n")
        for k in new_keys:
            v_msg = f" \n  ↪ _{k['verification']}_" if k.get('verification') else ""
            lines.append(f"- **{k['label']}** — `{k['preview']}`{v_msg}")
        lines.append("\nThey are now active in the system.")
    if already:
        labels = ", ".join(k["label"] for k in already)
        lines.append(f"\n_{labels} was already set with the same value._")

    return {
        "found": found,
        "reply": "\n".join(lines),
        "actions": actions,
    }


def _verify_key(env_var: str) -> Optional[str]:
    """Ping the respective API to ensure connection is working."""
    try:
        if env_var == "STRIPE_API_KEY":
            from integrations.stripe_client import get_stripe
            res = get_stripe().ping()
            return "✅ Verified: Stripe connection successful!" if res.get("status") == "ok" else f"⚠️ Warning: {res.get('detail', 'Validation failed')}"
        elif env_var == "AHREFS_API_KEY":
            from integrations.ahrefs_client import get_ahrefs
            res = get_ahrefs().ping()
            return "✅ Verified: Ahrefs connection successful!" if res.get("status") == "ok" else f"⚠️ Warning: Ahrefs validation failed"
        elif env_var == "TAVILY_API_KEY":
            from integrations.tavily_client import get_tavily
            res = get_tavily().ping()
            return "✅ Verified: Tavily connection successful!" if res.get("status") == "ok" else f"⚠️ Warning: Tavily validation failed"
        elif env_var in ("SUPABASE_ANON_KEY", "SUPABASE_URL"):
            # Only ping if both are somewhat present, else it will fail naturally
            if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"):
                from integrations.supabase_client import get_supabase
                res = get_supabase().ping()
                return "✅ Verified: Supabase connection successful!" if res.get("status") == "ok" else f"⚠️ Warning: Supabase validation failed"
        elif env_var == "TELEGRAM_BOT_TOKEN":
            import urllib.request
            import json
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("ok"):
                    from backend.api.integrations import _start_bot
                    from backend.core.database import SessionLocal
                    from backend.services.bot_service import create_bot, get_bot_by_token
                    
                    # Store in DB so it shows up in UI
                    with SessionLocal() as db:
                        bot = get_bot_by_token(db, token)
                        if not bot:
                            bot = create_bot(db, name=f"Telegram ({data['result']['first_name']})", platform="telegram", token=token)
                        _start_bot("telegram", token, bot_id=bot.id)
                    
                    return f"✅ Verified: Connected to **{data['result']['first_name']}**! Background bot process started."
        return None
    except Exception as e:
        return f"⚠️ Warning: Verification check hit an error ({str(e)})"


def _mask(value: str) -> str:
    """Mask a key value for safe display."""
    if len(value) <= 8:
        return "••••"
    return value[:6] + "••••" + value[-4:]


def _reload_singleton(env_var: str) -> None:
    """After storing a key, clear the lru_cache on the relevant client."""
    try:
        if env_var in ("STRIPE_API_KEY",):
            from integrations.stripe_client import get_stripe
            get_stripe.cache_clear()
        elif env_var in ("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_URL"):
            from integrations.supabase_client import get_supabase
            get_supabase.cache_clear()
        elif env_var == "TAVILY_API_KEY":
            from integrations.tavily_client import get_tavily
            get_tavily.cache_clear()
        elif env_var == "AHREFS_API_KEY":
            from integrations.ahrefs_client import get_ahrefs
            get_ahrefs.cache_clear()
    except Exception as e:
        logger.debug(f"[KeyInjector] Singleton reload skipped: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. GOOGLE JSON FILE ANALYSER
# ─────────────────────────────────────────────────────────────────────────────

# Gmail-related OAuth scopes
_GMAIL_SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
]

# Map of Google API scope prefixes to human-readable service names
_GOOGLE_SERVICE_MAP: Dict[str, str] = {
    "gmail":                    "Gmail",
    "drive":                    "Google Drive",
    "calendar":                 "Google Calendar",
    "youtube":                  "YouTube",
    "sheets":                   "Google Sheets",
    "docs":                     "Google Docs",
    "slides":                   "Google Slides",
    "admin.directory":          "Google Workspace Admin",
    "contacts":                 "Google Contacts",
    "tasks":                    "Google Tasks",
    "classroom":                "Google Classroom",
    "analytics":                "Google Analytics",
    "searchconsole":            "Google Search Console",
    "cloud-platform":           "Google Cloud Platform",
    "bigquery":                 "BigQuery",
    "pubsub":                   "Cloud Pub/Sub",
    "storage":                  "Google Cloud Storage",
    "compute":                  "Google Compute Engine",
    "firebase":                 "Firebase",
    "datastore":                "Cloud Datastore",
    "sqlservice":               "Cloud SQL",
    "spanner":                  "Cloud Spanner",
    "monitoring":               "Cloud Monitoring",
    "logging":                  "Cloud Logging",
    "cloudkms":                 "Cloud KMS",
    "iam":                      "IAM",
    "chatmessages":             "Google Chat",
}


def _detect_google_services(scopes: List[str]) -> List[str]:
    """Map scope URLs to human-readable Google service names."""
    detected = set()
    for scope in scopes:
        scope_lower = scope.lower()
        for key, name in _GOOGLE_SERVICE_MAP.items():
            if key in scope_lower:
                detected.add(name)
    return sorted(detected)


def _is_gmail_enabled(scopes: List[str]) -> bool:
    """Check if any Gmail scope is present."""
    for scope in scopes:
        for gmail_scope in _GMAIL_SCOPES:
            if gmail_scope in scope or "gmail" in scope.lower():
                return True
    return False


def analyze_google_json(content_text: str, filename: str = "file.json") -> Dict[str, Any]:
    """
    Analyse a Google OAuth2 client_secret JSON, service account JSON,
    or Application Default Credentials file.

    Returns a structured analysis with:
    - json_type:  'oauth_client', 'service_account', 'adc', 'unknown'
    - project_id
    - client_id
    - enabled_services: list of detected Google services
    - gmail_enabled: bool
    - actions:  list of auto-actions taken (e.g. Gmail connector activated)
    - reply:    human-readable summary
    """
    try:
        data = json.loads(content_text)
    except json.JSONDecodeError:
        return {
            "is_google_json": False,
            "error": "Invalid JSON",
            "reply": f"The file `{filename}` is not valid JSON.",
        }

    # ── Identify JSON type ─────────────────────────────────────────────
    json_type = "unknown"
    client_id = ""
    project_id = ""
    scopes: List[str] = []
    allowed_scopes: List[str] = []

    # Type 1: OAuth2 client_secret (downloaded from Google Cloud Console)
    if "installed" in data or "web" in data:
        json_type = "oauth_client"
        root = data.get("installed") or data.get("web") or {}
        client_id = root.get("client_id", "")
        project_id = root.get("project_id", "")
        # Authorized scopes aren't embedded in the OAuth JSON itself —
        # they are requested at runtime. We look for any hints.
        # Some developers put them under a custom "scopes" key
        scopes = data.get("scopes", root.get("scopes", []))

    # Type 2: Service Account JSON
    elif data.get("type") == "service_account":
        json_type = "service_account"
        client_id = data.get("client_id", data.get("client_email", ""))
        project_id = data.get("project_id", "")
        scopes = data.get("scopes", [])

    # Type 3: Application Default Credentials
    elif data.get("type") in ("authorized_user", "external_account", "impersonated_service_account"):
        json_type = "adc"
        client_id = data.get("client_id", "")
        project_id = data.get("quota_project_id", "")
        scopes = data.get("scopes", [])

    elif not client_id and not project_id:
        # Not a Google JSON we recognise
        return {
            "is_google_json": False,
            "error": "Not a recognised Google JSON format",
            "reply": (
                f"`{filename}` doesn't look like a Google credentials file.\n"
                "Expected: OAuth2 client_secret.json, service account key, or ADC file."
            ),
        }

    # ── Detect services from scopes ───────────────────────────────────
    enabled_services = _detect_google_services(scopes)
    gmail_enabled = _is_gmail_enabled(scopes)

    # ── Auto-actions ───────────────────────────────────────────────────
    actions_taken = []

    # Save Google credentials path to .env
    _persist_key("GOOGLE_JSON_TYPE", json_type)
    if project_id:
        _persist_key("GOOGLE_CLOUD_PROJECT", project_id)
    if client_id:
        _persist_key("GOOGLE_CLIENT_ID_DETECTED", client_id)
    actions_taken.append("stored:GOOGLE_JSON_TYPE")

    # Gmail-specific auto-connect
    if gmail_enabled or json_type in ("oauth_client", "service_account"):
        # For oauth_client JSONs, Gmail is typically the reason they're uploaded
        # Mark Gmail as enabled so the connector can prompt for OAuth
        _persist_key("GMAIL_ENABLED", "true")
        _persist_key("GOOGLE_JSON_UPLOADED", "true")
        actions_taken.append("gmail:enabled")
        gmail_enabled = True  # Force true for OAuth client files

    # ── Build reply ────────────────────────────────────────────────────
    reply_lines = [
        f"## Google Credentials Analysis: `{filename}`\n",
        f"**Type:** `{json_type}`",
    ]
    if project_id:
        reply_lines.append(f"**Project ID:** `{project_id}`")
    if client_id:
        reply_lines.append(f"**Client ID:** `{client_id[:20]}...`" if len(client_id) > 20 else f"**Client ID:** `{client_id}`")

    if enabled_services:
        reply_lines.append(f"\n**Detected Google APIs/Services:**")
        for svc in enabled_services:
            reply_lines.append(f"- {svc}")
    else:
        reply_lines.append(
            "\n**Note:** No explicit scopes found in this file — "
            "scopes are typically requested at runtime via OAuth flow."
        )

    # Gmail status
    if gmail_enabled:
        reply_lines.append(
            "\n**Gmail: ENABLED**\n"
            "I've activated the Gmail connector. "
            "To complete the connection, you'll need to run the OAuth flow:\n\n"
            "```\nGET /api/oauth/google/connect?scopes=gmail\n```\n"
            "or click **Connect Gmail** in the Integrations panel."
        )
    else:
        reply_lines.append(
            "\n**Gmail: NOT detected in this JSON.**\n"
            "If you need Gmail access, re-download the credentials from Google Cloud Console "
            "and ensure the Gmail API is enabled in your project."
        )

    if json_type == "service_account":
        reply_lines.append(
            "\n> **Note:** Service accounts can access Gmail only via **domain-wide delegation** "
            "(Google Workspace). Standard Gmail user accounts must use OAuth2 (client_secret.json)."
        )

    return {
        "is_google_json": True,
        "json_type": json_type,
        "project_id": project_id,
        "client_id": client_id,
        "enabled_services": enabled_services,
        "gmail_enabled": gmail_enabled,
        "actions": actions_taken,
        "reply": "\n".join(reply_lines),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. GENERIC FILE ANALYSER (entry point called from chat flow)
# ─────────────────────────────────────────────────────────────────────────────

def analyze_uploaded_file(filename: str, content_text: str, file_type: str = "") -> Optional[Dict[str, Any]]:
    """
    Determine if an uploaded file requires special handling.
    Currently handles:
      - Google JSON files (OAuth, service account, ADC)
      - Plain text files that look like they contain API keys

    Returns a result dict with a 'reply' key if the file was handled,
    or None if normal file handling should proceed.
    """
    fn_lower = filename.lower()

    # ── Google JSON detection ──────────────────────────────────────────
    is_json = fn_lower.endswith(".json") or file_type in ("application/json", "text/json")
    if is_json and content_text.strip().startswith("{"):
        try:
            data = json.loads(content_text)
        except Exception:
            return None

        # Heuristics: look for Google-specific keys
        google_indicators = {
            "client_id", "client_secret", "project_id",
            "type", "token_uri", "auth_uri",
            "installed", "web", "private_key_id",
        }
        present = set(data.keys())
        if google_indicators & present:
            result = analyze_google_json(content_text, filename)
            if result.get("is_google_json"):
                return result

        # Non-Google JSON: scan for API keys in the text
        key_result = detect_and_store_keys(content_text)
        if key_result["found"]:
            return {"reply": key_result["reply"], "actions": key_result["actions"]}

    # ── Plain text / .env-style files ─────────────────────────────────
    elif fn_lower.endswith((".txt", ".env", ".conf", ".cfg", ".ini")):
        key_result = detect_and_store_keys(content_text)
        if key_result["found"]:
            return {
                "reply": f"Scanned `{filename}` and found keys:\n" + key_result["reply"],
                "actions": key_result["actions"],
            }

    return None
