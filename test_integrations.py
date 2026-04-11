"""
test_integrations.py
====================
Quick connectivity test for Supabase, Tavily, and Stripe.

Usage:
    python test_integrations.py

Output:  A clear pass/fail summary for each integration.
"""

import sys
import os
import io

# Fix Windows console UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env manually (no dotenv dependency required)
def _load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key and key not in os.environ:
                os.environ[key] = val

_load_env()

# ─────────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"

def _ok(label, detail=""):
    suffix = f"  -- {detail}" if detail else ""
    print(f"  {GREEN}[PASS]{RESET}  {BOLD}{label}{RESET}{suffix}")

def _fail(label, detail=""):
    suffix = f"  -- {detail}" if detail else ""
    print(f"  {RED}[FAIL]{RESET}  {BOLD}{label}{RESET}{suffix}")

def _warn(label, detail=""):
    suffix = f"  -- {detail}" if detail else ""
    print(f"  {YELLOW}[SKIP]{RESET}  {BOLD}{label}{RESET}{suffix}")

# ─────────────────────────────────────────────────────────────────────
print(f"\n{CYAN}{BOLD}{'='*55}")
print("  DreamAgent Integration Test Suite")
print(f"{'='*55}{RESET}\n")

results = []

# ── 1. Supabase ────────────────────────────────────────────────────
print(f"{BOLD}[1] Supabase{RESET}")
url = os.getenv("SUPABASE_URL", "")
key = os.getenv("SUPABASE_ANON_KEY", "") or os.getenv("SUPABASE_SERVICE_KEY", "")

if not url or not key:
    _warn("Supabase credentials", "SUPABASE_URL or key missing from .env")
    results.append(("Supabase", "skipped"))
else:
    print(f"     URL  : {url}")
    print(f"     KEY  : {key[:24]}...")
    try:
        from integrations.supabase_client import SupabaseClient
        sb = SupabaseClient(url=url, key=key)
        if not sb.available:
            _warn("Supabase SDK", "supabase package not installed -- run: pip install supabase")
            results.append(("Supabase", "skipped"))
        else:
            ping = sb.ping()
            if ping.get("status") == "ok":
                _ok("Supabase connection", ping.get("note", "connected"))
                results.append(("Supabase", "ok"))
            else:
                _fail("Supabase connection", ping.get("detail", "unknown error"))
                results.append(("Supabase", "fail"))
    except Exception as e:
        _fail("Supabase connection", str(e))
        results.append(("Supabase", "fail"))
print()

# ── 2. Tavily ─────────────────────────────────────────────────────
print(f"{BOLD}[2] Tavily{RESET}")
tavily_key = os.getenv("TAVILY_API_KEY", "")

if not tavily_key:
    _warn("Tavily credentials", "TAVILY_API_KEY missing from .env")
    results.append(("Tavily", "skipped"))
else:
    print(f"     KEY  : {tavily_key[:24]}...")
    try:
        from integrations.tavily_client import TavilyClient
        tv = TavilyClient(api_key=tavily_key)
        if not tv.available:
            _warn("Tavily SDK", "tavily-python not installed -- run: pip install tavily-python")
            results.append(("Tavily", "skipped"))
        else:
            ping = tv.ping()
            if ping.get("status") == "ok":
                _ok("Tavily search", f"returned {ping.get('result_count', '?')} results")
                results.append(("Tavily", "ok"))
            else:
                _fail("Tavily search", ping.get("detail", "unknown"))
                results.append(("Tavily", "fail"))
    except Exception as e:
        _fail("Tavily connection", str(e))
        results.append(("Tavily", "fail"))
print()

# ── 3. Stripe ─────────────────────────────────────────────────────
print(f"{BOLD}[3] Stripe{RESET}")
stripe_key = os.getenv("STRIPE_API_KEY", "")

if not stripe_key:
    _warn("Stripe credentials", "STRIPE_API_KEY not set in .env  (add sk_live_... or sk_test_...)")
    results.append(("Stripe", "skipped"))
else:
    print(f"     KEY  : {stripe_key[:24]}...")
    try:
        from integrations.stripe_client import StripeClient
        st = StripeClient(api_key=stripe_key)
        if not st.available:
            _warn("Stripe SDK", "stripe package not installed -- run: pip install stripe")
            results.append(("Stripe", "skipped"))
        else:
            ping = st.ping()
            if ping.get("status") == "ok":
                _ok("Stripe connection", "API reachable")
                results.append(("Stripe", "ok"))
            else:
                _fail("Stripe connection", ping.get("detail", "unknown"))
                results.append(("Stripe", "fail"))
    except Exception as e:
        _fail("Stripe connection", str(e))
        results.append(("Stripe", "fail"))
print()

# ── Summary ───────────────────────────────────────────────────────
print(f"{CYAN}{BOLD}{'—'*55}")
print("  SUMMARY")
print(f"{'—'*55}{RESET}")

passed  = sum(1 for _, s in results if s == "ok")
failed  = sum(1 for _, s in results if s == "fail")
skipped = sum(1 for _, s in results if s == "skipped")

for name, status in results:
    if status == "ok":
        color = GREEN; label = "PASS"
    elif status == "fail":
        color = RED; label = "FAIL"
    else:
        color = YELLOW; label = "SKIP"
    print(f"  {color}[{label}]{RESET}  {BOLD}{name}{RESET}")

print()
print(f"  Passed: {GREEN}{passed}{RESET}  |  Failed: {RED}{failed}{RESET}  |  Skipped: {YELLOW}{skipped}{RESET}")
print()

if failed:
    print(f"{RED}Some integrations failed -- check your .env keys above.{RESET}\n")
    sys.exit(1)
elif skipped == len(results):
    print(f"{YELLOW}All integrations skipped -- fill in your API keys in .env{RESET}\n")
else:
    print(f"{GREEN}All tested integrations are healthy!{RESET}\n")
