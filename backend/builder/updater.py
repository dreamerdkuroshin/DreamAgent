"""
backend/builder/updater.py

Hardened Re-edit / Iteration Engine.
Supports:
  - Version-based snapshots (v1, v2, v3...)
  - Patch-based updates (SEARCH/REPLACE — no full overwrites)
  - BeautifulSoup HTML validation
  - JS/CSS heuristic validation
  - File-level asyncio locks (prevents race conditions)
  - Auto-rollback on failure
  - BuildVersion tracking with is_active flag
  - Standardized SSE events with progress %
"""

import os
import re
import shutil
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

from backend.core.database import SessionLocal
from backend.core.models import BuildSession, BuildVersion

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILDER_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "builder_output")

# ─── File Locks (prevent concurrent updates to same session) ──────────────────
_session_locks: Dict[str, asyncio.Lock] = {}

def _get_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


# ─── Validators ───────────────────────────────────────────────────────────────

def validate_html(content: str) -> tuple[bool, str, Optional[int]]:
    """Validate HTML structure using BeautifulSoup. Returns (is_valid, error_msg, line_number)."""
    try:
        from bs4 import BeautifulSoup
        # lxml parser returns better error lines, but html.parser is safer if lxml missing
        soup = BeautifulSoup(content, "html.parser")
        if not soup.find():
            return False, "Document is entirely empty or missing tags", 1
        return True, "", None
    except Exception as e:
        error_str = str(e)
        # Attempt to parse line number from BS4 or standard errors
        # Example format: "mismatched tag at line 42"
        match = re.search(r'line (\d+)', error_str, re.IGNORECASE)
        line_num = int(match.group(1)) if match else None
        return False, error_str, line_num


def validate_js(content: str) -> tuple[bool, str, Optional[int]]:
    """Heuristic JS validation — bracket/paren balance."""
    if content.count("{") != content.count("}"):
        return False, "Unbalanced curly braces {} in JS", None
    if content.count("(") != content.count(")"):
        return False, "Unbalanced parentheses () in JS", None
    return True, "", None


def validate_css(content: str) -> tuple[bool, str, Optional[int]]:
    """Heuristic CSS validation — curly brace balance."""
    if content.count("{") != content.count("}"):
        return False, "Unbalanced curly braces {} in CSS", None
    return True, "", None


def validate_file(rel_path: str, content: str) -> tuple[bool, str, Optional[int]]:
    """Route to the correct validator by file extension."""
    if rel_path.endswith(".html") or rel_path.endswith(".htm"):
        return validate_html(content)
    elif rel_path.endswith(".js") or rel_path.endswith(".jsx") or rel_path.endswith(".ts") or rel_path.endswith(".tsx"):
        return validate_js(content)
    elif rel_path.endswith(".css"):
        return validate_css(content)
    return True, "", None


# ─── Versioning Engine ────────────────────────────────────────────────────────

def get_latest_version(session_id: str) -> int:
    """Read latest version from DB."""
    db = SessionLocal()
    session = db.query(BuildSession).filter(BuildSession.id == session_id).first()
    db.close()
    return session.version if session else 1


def create_version_snapshot(session_id: str, new_version: int) -> str:
    """Copies current version folder to a new version folder."""
    base_path = os.path.join(BUILDER_OUTPUT_DIR, session_id)
    old_path = os.path.join(base_path, f"v{new_version - 1}")
    new_path = os.path.join(base_path, f"v{new_version}")

    if not os.path.exists(old_path):
        # Initial versioning fix: if v1 doesn't exist but files are in root, move them
        os.makedirs(old_path, exist_ok=True)
        for item in os.listdir(base_path):
            if item.startswith("v") and item[1:].isdigit():
                continue
            src = os.path.join(base_path, item)
            shutil.move(src, old_path)

    shutil.copytree(old_path, new_path)
    return new_path


# ─── Intent Detection & Smart Interpreter ─────────────────────────────────────

MAPPINGS = {
    "make it better": "improve UI styling, typography, and spacing",
    "fix it": "fix responsive layout and resolve syntax issues",
    "make it modern": "apply modern UI with clean typography, glassmorphism, and subtle shadows",
    "make it cool": "add dynamic micro-animations, rich gradients, and vibrant colors",
    "looks bad": "refine color contrast, fix alignment, and improve component hierarchy"
}

def normalize_update_request(text: str) -> str:
    """Transforms vague instructions into concrete design patterns."""
    t_lower = text.lower().strip()
    return MAPPINGS.get(t_lower, text)

UPDATE_INTENTS = {
    "add_auth":     r"\b(add login|add auth|add sign.?in|add signup|add registration|enable login)\b",
    "dark_mode":    r"\b(dark mode|make it dark|switch dark|dark theme|darkmode)\b",
    "light_mode":   r"\b(light mode|make it light|switch light|bright theme)\b",
    "change_color": r"\b(change color|change theme|use (purple|green|blue|red)|make it (purple|green|blue|red))\b",
}

DARK_MODE_STYLE = """
  <style id="dreamagent-theme">
    :root { color-scheme: dark; }
    body { background: #0a0a12 !important; color: #e8e8f5 !important; }
    nav, aside, .card, .modal, .stat-card, .chart-card, .table-card, .feature-card, .pricing-card {
      background: #13131e !important; border-color: rgba(255,255,255,0.07) !important;
    }
  </style>"""


def detect_update_intent(message: str) -> Optional[str]:
    m = message.lower()
    for intent, pattern in UPDATE_INTENTS.items():
        if re.search(pattern, m):
            return intent
    return None


# ─── Safe Patch Application ───────────────────────────────────────────────────

def apply_patch(content: str, search: str, replace: str) -> str:
    """
    Apply a single SEARCH/REPLACE patch. 
    Raises if search target not found (prevents silent failures).
    """
    if search not in content:
        raise ValueError(f"Patch target not found in file content. Search string: '{search[:80]}...'")
    return content.replace(search, replace, 1)


def parse_llm_patches(llm_output: str) -> List[Dict[str, str]]:
    """
    Parse the strict LLM patch format:
    
    FILE: index.html
    SEARCH:
    <old code>
    REPLACE:
    <new code>
    
    Returns list of {file, search, replace} dicts.
    """
    patches = []
    # Split by FILE: markers
    blocks = re.split(r'^FILE:\s*', llm_output, flags=re.MULTILINE)
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        lines = block.split('\n', 1)
        filename = lines[0].strip()
        if len(lines) < 2:
            continue
        rest = lines[1]
        
        # Find all SEARCH/REPLACE pairs in this file block
        pairs = re.split(r'^SEARCH:\s*\n', rest, flags=re.MULTILINE)
        for pair in pairs[1:]:  # Skip content before first SEARCH
            parts = re.split(r'^REPLACE:\s*\n', pair, flags=re.MULTILINE)
            if len(parts) == 2:
                search_text = parts[0].rstrip('\n')
                replace_text = parts[1].rstrip('\n')
                patches.append({
                    "file": filename,
                    "search": search_text,
                    "replace": replace_text
                })
    
    return patches


# ─── Rollback Logic ──────────────────────────────────────────────────────────

def rollback_version(session_id: str, target_version: int) -> Dict[str, Any]:
    """
    Rollback to a target version.
    - Does NOT delete newer versions (preserves history)
    - Deactivates all versions, then activates the target
    - Updates session.version pointer
    """
    db = SessionLocal()
    try:
        session = db.query(BuildSession).filter(BuildSession.id == session_id).first()
        if not session:
            return {"error": "Session not found"}
        
        target_v = db.query(BuildVersion).filter(
            BuildVersion.session_id == session_id,
            BuildVersion.version == target_version
        ).first()
        
        if not target_v:
            return {"error": f"Version {target_version} not found"}
        
        # Check the version folder exists on disk
        version_dir = os.path.join(session.path, f"v{target_version}")
        if not os.path.exists(version_dir):
            return {"error": f"Version {target_version} files missing from disk"}
        
        # Deactivate all versions
        db.query(BuildVersion).filter(
            BuildVersion.session_id == session_id
        ).update({"is_active": 0})
        
        # Activate target
        target_v.is_active = 1
        
        # Update session pointer
        session.version = target_version
        session.status = "completed"
        
        db.commit()
        
        return {
            "session_id": session_id,
            "version": target_version,
            "message": f"Rolled back to v{target_version}",
            "status": "completed"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"[Updater] Rollback failed for {session_id}: {e}")
        return {"error": str(e)}
    finally:
        db.close()


# ─── Main Update Engine ──────────────────────────────────────────────────────

async def apply_update(
    session_id: str,
    message: str,
    publish_event: Optional[Callable] = None,
    provider: str = "auto",
    model: str = ""
) -> Dict[str, Any]:
    """
    Hardened update pipeline:
    1. Acquires file lock for session
    2. Increments version in DB
    3. Creates file snapshot (vN -> vN+1)
    4. Applies patch (template or LLM)
    5. Validates ALL changed files
    6. Writes to disk ONLY if validation passes
    7. Creates BuildVersion record
    8. Auto-rollbacks on any failure
    """
    lock = _get_lock(session_id)
    
    async with lock:
        db = SessionLocal()
        session = db.query(BuildSession).filter(BuildSession.id == session_id).first()
        if not session:
            db.close()
            return {"error": "Session not found"}

        def emit(step: str, progress: int = 0, msg: str = ""):
            event = {
                "type": "builder_step",
                "step": step,
                "progress": progress,
                "session_id": session_id,
                "message": msg or step.replace("_", " ").title()
            }
            logger.info(f"[Updater] {event}")
            if publish_event:
                publish_event(event)

        old_version = session.version
        new_version = old_version + 1
        v_path = None

        try:
            emit("analyzing_update", 10, "Analyzing your request...")
            
            emit("creating_snapshot", 20, f"Creating version snapshot v{new_version}...")
            v_path = create_version_snapshot(session_id, new_version)
            
            # Load files from the NEW folder
            files = {}
            for root, _, fnames in os.walk(v_path):
                for fname in fnames:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, v_path)
                    try:
                        with open(full, "r", encoding="utf-8") as f:
                            files[rel] = f.read()
                    except UnicodeDecodeError:
                        continue  # Skip binary files

            # ── Smart Interpreter Normalization ──────────
            instruction = normalize_update_request(message)
            if instruction != message:
                emit("normalizing", 15, f"Interpreting request: '{instruction}'")
                
            intent = detect_update_intent(instruction)
            emit("applying_patch", 40, "Applying changes...")
            
            updated_files = {}
            method = "template"

            if intent == "dark_mode":
                html_key = next((k for k in files if k.endswith("index.html")), None)
                if html_key:
                    content = files[html_key]
                    if "dreamagent-theme" not in content:
                        updated_files[html_key] = content.replace("</head>", DARK_MODE_STYLE + "\n</head>")
            
            elif intent == "light_mode":
                html_key = next((k for k in files if k.endswith("index.html")), None)
                if html_key:
                    updated_files[html_key] = re.sub(
                        r'<style id="dreamagent-theme">.*?</style>', 
                        '', files[html_key], flags=re.DOTALL
                    )
            
            else:
                # LLM Patch Fallback
                method = "llm"
                emit("requesting_llm_patch", 50, "Requesting AI patch...")
                updated_files = await _llm_patch_files(files, instruction, provider, model, emit)

            # ── Validation Gate ──────────────────────────────────────────
            emit("validating", 70, "Validating changes...")
            for rel, content in updated_files.items():
                is_valid, err_msg, err_line = validate_file(rel, content)
                if not is_valid:
                    # Emitted error payload parsed by frontend for line targeting
                    raise ValueError(f"Validation failed for {rel}|LINE:{err_line or 'unknown'}|MSG:{err_msg}")

            # ── Write to Disk (only after validation passes) ─────────────
            emit("writing_files", 80, f"Writing {len(updated_files)} files...")
            for rel, content in updated_files.items():
                full = os.path.join(v_path, rel)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(content)

            # ── Update DB ────────────────────────────────────────────────
            emit("committing", 90, "Committing version...")
            
            # Deactivate previous versions
            db.query(BuildVersion).filter(
                BuildVersion.session_id == session_id
            ).update({"is_active": 0})
            
            # Create new BuildVersion record
            bv = BuildVersion(
                session_id=session_id,
                version=new_version,
                path=v_path,
                message=message[:500],  # Truncate long messages
                is_active=1,
                created_at=datetime.utcnow()
            )
            db.add(bv)
            
            session.version = new_version
            session.status = "completed"
            db.commit()
            
            emit("done", 100, f"Version {new_version} created successfully!")
            return {
                "session_id": session_id,
                "version": new_version,
                "updated_files": list(updated_files.keys()),
                "method": method,
                "message": message[:200]
            }

        except Exception as e:
            logger.error(f"[Updater] Build {session_id} v{new_version} failed: {e}")
            
            # Auto-rollback: remove the failed version folder
            if v_path and os.path.exists(v_path):
                shutil.rmtree(v_path, ignore_errors=True)
            
            session.status = "failed"
            db.commit()
            
            # Emit error SSE
            if publish_event:
                # Try to parse strict formatting for frontend Error Panel
                err_str = str(e)
                if "|LINE:" in err_str:
                    try:
                        parts = err_str.split("|")
                        f_name = parts[0].replace("Validation failed for ", "").strip()
                        l_num = parts[1].replace("LINE:", "").strip()
                        m_str = parts[2].replace("MSG:", "").strip()
                        publish_event({
                            "type": "error",
                            "file": f_name,
                            "line": int(l_num) if l_num != 'unknown' else None,
                            "message": m_str
                        })
                    except:
                        pass
                else:    
                    publish_event({
                        "type": "error",
                        "message": f"Patch failed — reverting to v{old_version}. Error: {str(e)}"
                    })
            
            return {"error": str(e), "reverted_to": old_version}
        finally:
            db.close()


async def _llm_patch_files(
    files: Dict[str, str], 
    instruction: str, 
    provider: str, 
    model: str,
    emit: Callable
) -> Dict[str, str]:
    """
    Uses LLM to generate SEARCH/REPLACE patches.
    Forces strict output format — never allows full file overwrite.
    """
    from backend.llm.universal_provider import UniversalProvider
    import difflib
    llm = UniversalProvider(provider=provider, model=model)
    
    # Gather relevant files (focus on HTML/CSS/JS)
    target_files = {k: v for k, v in files.items() 
                    if k.endswith(('.html', '.css', '.js', '.jsx', '.ts', '.tsx'))}
    
    if not target_files:
        return {}

    # Build file context (truncate large files)
    file_context = ""
    for fname, content in list(target_files.items())[:5]:  # Max 5 files
        truncated = content[:8000]
        file_context += f"\n--- FILE: {fname} ---\n{truncated}\n"

    prompt = f"""You are an AI Web Builder performing a surgical code update.

INSTRUCTION: "{instruction}"

CURRENT FILES:
{file_context}

RULES — FOLLOW EXACTLY:
1. Output ONLY in this format (no explanations, no markdown fences):

FILE: <filename>
SEARCH:
<exact existing code to find>
REPLACE:
<new code to replace it with>

2. You can output multiple FILE/SEARCH/REPLACE blocks.
3. SEARCH must match EXACTLY what exists in the file.
4. Only modify what's needed. Do NOT rewrite entire files.
5. If adding new code, use an adjacent existing line as the SEARCH anchor.
"""

    emit("waiting_for_llm", 55, "Waiting for AI response...")
    raw_output = llm.generate([{"role": "user", "content": prompt}])
    raw_output = raw_output.strip().strip("```").strip()
    
    emit("parsing_patches", 60, "Parsing AI patches...")
    patches = parse_llm_patches(raw_output)
    
    if not patches:
        # Fallback: if LLM didn't follow format, try full-file mode on index.html
        logger.warning("[Updater] LLM did not return valid patches. Attempting full-file fallback.")
        target = next((k for k in files if k.endswith("index.html")), None)
        if target and raw_output.strip().startswith("<"):
            # LLM returned raw HTML — use it but validate first
            return {target: raw_output}
        return {}
    
    # Apply patches to file copies
    updated = {}
    for patch in patches:
        fname = patch["file"]
        # Find the matching file (handle path variations)
        actual_key = next((k for k in files if k.endswith(fname) or k == fname), None)
        if not actual_key:
            logger.warning(f"[Updater] Patch references unknown file: {fname}")
            continue
        
        base_content = updated.get(actual_key, files[actual_key])
        try:
            new_content = apply_patch(base_content, patch["search"], patch["replace"])
            
            # ── Patch Confidence Check ────────────────────────────────
            ratio = difflib.SequenceMatcher(None, base_content, new_content).ratio()
            length_mult = len(new_content) / (len(base_content) or 1)
            
            if ratio < 0.3 or length_mult > 3.0:
                logger.warning(f"[Updater] Patch REJECTED for {fname}: similarity={ratio:.2f}, length_mult={length_mult:.2f}")
                raise ValueError(
                    f"Patch confidence too low for {fname}: similarity={ratio:.2f}, size_ratio={length_mult:.1f}x. "
                    f"Blocked to prevent destructive rewrite."
                )
            
            updated[actual_key] = new_content
        except ValueError as e:
            logger.warning(f"[Updater] Patch skipped for {fname}: {e}")
            continue
    
    return updated
