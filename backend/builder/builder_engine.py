"""
backend/builder/builder_engine.py
Main entry point for website/app code generation.
"""

import os
import json
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Callable, Optional

from backend.builder.generators import (
    landing_page,
    static_store,
    fullstack_ecommerce,
    dashboard,
    cinematic
)
from backend.core.database import SessionLocal
from backend.core.models import BuildSession, BuildVersion
from backend.core.context_manager import get_agent_context, save_agent_context

logger = logging.getLogger(__name__)

# The base directory where all built projects are saved.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILDER_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "builder_output")


@dataclass
class BuildResult:
    session_id: str
    output_path: str
    files: Dict[str, str]
    preview_url: str = ""
    preview_html: str = ""
    error: Optional[str] = None


async def build_website(prefs: Dict[str, Any], publish_event: Optional[Callable] = None) -> BuildResult:
    """
    Core Builder Engine function.
    Given parsed preferences, generate the right site and save it to disk.
    
    Args:
        prefs: Dictionary containing 'design', 'type', 'backend', 'features'
        publish_event: Optional callback to stream SSE events back to the UI
    """
    
    def emit_progress(step: str, progress: int = 0, message: str = "", sid: str = None):
        logger.info(f"[Builder] {step}: {message or step}")
        if publish_event:
            payload = {
                "type": "builder_step",
                "step": step,
                "progress": progress,
                "message": message or step
            }
            if sid:
                payload["session_id"] = sid
            publish_event(payload)
            
    try:
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        emit_progress("initializing", 3, "Initializing builder environment...", sid=session_id)
        
        
        # Physical versioning: v1 is the initial build
        session_base = os.path.join(BUILDER_OUTPUT_DIR, session_id)
        session_path = os.path.join(session_base, "v1")
        
        os.makedirs(session_path, exist_ok=True)
            
        site_type = prefs.get("type", "landing")
        needs_backend = prefs.get("backend", False)

        # ── Normalize ALL prefs fields once ──────────────────────────
        # features: UI may send list ["auth","payment"] or dict {"auth": True}
        raw_features = prefs.get("features", {})
        if isinstance(raw_features, list):
            prefs["features"] = {f.lower(): True for f in raw_features if isinstance(f, str)}
        elif not isinstance(raw_features, dict):
            prefs["features"] = {}

        # database: UI sends {"enabled": bool, "type": "sqlite"} — extract to flat string
        raw_db = prefs.get("database")
        if isinstance(raw_db, dict):
            db_enabled = raw_db.get("enabled", False)
            db_type_str = raw_db.get("type") or raw_db.get("name") or "sqlite"
            prefs["database"] = db_type_str if db_enabled else None
            # Also set backend flag from database.enabled if not already set
            if db_enabled and not prefs.get("backend"):
                prefs["backend"] = True
        elif raw_db is not None and not isinstance(raw_db, str):
            prefs["database"] = None  # unknown shape, skip safely

        # connections: ensure it's always a flat list of strings
        raw_conn = prefs.get("connections", [])
        if isinstance(raw_conn, str):
            prefs["connections"] = [raw_conn] if raw_conn else []
        elif not isinstance(raw_conn, list):
            prefs["connections"] = []
        else:
            # filter out any non-string entries
            prefs["connections"] = [c for c in raw_conn if isinstance(c, str)]

        # design: ensure string
        if not isinstance(prefs.get("design"), str):
            prefs["design"] = "modern"

        # type: ensure string (site type)
        if not isinstance(prefs.get("type"), str):
            prefs["type"] = "landing"
        site_type = prefs["type"]

        # backend: ensure bool
        prefs["backend"] = bool(prefs.get("backend", False))
        needs_backend = prefs["backend"]
        # ─────────────────────────────────────────────────────────────

        emit_progress("initializing", 5, f"Parsing preferences ({prefs.get('design', 'modern').title()} {site_type})...", sid=session_id)
        files = {}
        
        # ── Multi-Agent Path (when provider specified) ───────────────
        provider = prefs.get("provider", "auto")
        model = prefs.get("model", "")
        use_multi_agent = prefs.get("multi_agent", False)
        
        # Route complex types to Multi-Agent LLM pipeline
        # ecommerce, dashboard, cinematic -> fast template path
        # everything else -> multi-agent LLM
        complex_types = [
            "management", "social", "gaming", "edtech", "booking",
            "chat", "corporate", "streaming", "saas", "utility", "ai",
            "portfolio", "blog", "business", "custom"
        ]
        if site_type in complex_types:
            use_multi_agent = True
        
        if use_multi_agent:
            emit_progress("multi_agent_start", 10, "Starting multi-agent build pipeline...", sid=session_id)
            from backend.builder.multi_agent_builder import multi_agent_build
            raw_request = prefs.get("raw_request", str(prefs))
            ma_files, spec = await multi_agent_build(raw_request, prefs, provider=provider, model=model, publish_event=publish_event)
            if ma_files:
                files = ma_files
                emit_progress("multi_agent_complete", 78, f"Pipeline generated {len(files)} files", sid=session_id)

        # ── Template Path (fast, deterministic) ──────────────────────
        if not files:
            if site_type == "ecommerce":
                if needs_backend:
                    emit_progress("generating", 30, "Scaffolding Full Stack E-commerce...", sid=session_id)
                    files = fullstack_ecommerce.generate(prefs)
                else:
                    emit_progress("generating", 30, "Generating Static Store UI...", sid=session_id)
                    files = static_store.generate(prefs)
                    
            elif site_type == "dashboard":
                emit_progress("generating", 30, "Generating Admin Dashboard...", sid=session_id)
                files = dashboard.generate(prefs)

            elif site_type == "cinematic":
                emit_progress("generating", 30, "Generating Cinematic Showcase...", sid=session_id)
                files = cinematic.generate(prefs)
                
            else:
                emit_progress("generating", 30, "Generating Landing Page...", sid=session_id)
                files = landing_page.generate(prefs)

        if not files:
            raise ValueError("Failed to generate any files.")


        # Auto-generate README.md with run instructions
        readme_content = _generate_readme(prefs, site_type, needs_backend)
        files["README.md"] = readme_content

        emit_progress("writing", 90, f"Writing {len(files)} files to disk...", sid=session_id)

        # Safely write files to the session output directory
        for relative_path, content in files.items():
            # Prevent directory traversal in generator output keys
            if ".." in relative_path or relative_path.startswith("/"):
                 continue
                 
            safe_file_path = os.path.abspath(os.path.join(session_path, relative_path))
            
            # Double check it remains inside the session path
            if not safe_file_path.startswith(os.path.abspath(session_path)):
                continue

            # Ensure subdirectories exist (e.g., backend/routes/)
            os.makedirs(os.path.dirname(safe_file_path), exist_ok=True)
            
            with open(safe_file_path, "w", encoding="utf-8") as f:
                f.write(content)

        emit_progress("connections", 92, "Setting up database and connections...", sid=session_id)
        from backend.builder.connections import connections_registry
        
        db_type = prefs.get("database")
        if db_type:
            connections_registry.apply(db_type, {"path": session_path, "files": files})

        # Not all integrations are databases, any connections specified also get applied
        for conn_name in prefs.get("connections", []):
            connections_registry.apply(conn_name, {"path": session_path, "files": files})

        emit_progress("done", 95, "Build completed successfully.", sid=session_id)

        # --- DB Recording & PCO Sync ---
        db = SessionLocal()
        new_session = BuildSession(
            id=session_id,
            user_id="local_user",
            bot_id="local_bot",
            project_name=f"{prefs.get('type', 'Landing').title()} Project",
            project_type=prefs.get("type", "landing"),
            design=prefs.get("design", ""),
            version=1,
            status="completed",
            has_backend=1 if needs_backend else 0,
            features=prefs.get("features", {}),
            file_count=len(files),
            path=session_base
        )
        db.add(new_session)
        db.flush()

        # Create initial BuildVersion record
        initial_version = BuildVersion(
            session_id=session_id,
            version=1,
            path=session_path,
            message="Initial build",
            is_active=1,
            created_at=datetime.utcnow()
        )
        db.add(initial_version)
        db.commit()
        db.close()

        # Update PCO last_build and richer context
        pco = get_agent_context("local_user", "local_bot")
        pco["last_build"] = {
            "session_id": session_id,
            "project_name": f"{prefs.get('design', '').title()} Project",
            "project_type": prefs.get("type", "landing"),
            "design": prefs.get("design", ""),
            "version": 1,
            "path": session_base
        }
        
        feats = prefs.get("features", {})
        if isinstance(feats, list):
            feat_list = feats
        else:
            feat_list = [k for k, v in feats.items() if v]

        # Initialize Rich Builder Context
        pco["builder_context"] = {
            "framework": "html/css/js",
            "style": prefs.get("design", ""),
            "components": [site_type] + feat_list,
            "last_actions": ["initial project scaffold"]
        }
        
        save_agent_context("local_user", "local_bot", pco)

        # Try to find a previewable HTML file
        preview_html = files.get("index.html") or files.get("frontend/index.html", "")
        
        result = BuildResult(
            session_id=session_id,
            output_path=session_path,
            files=files,
            preview_html=preview_html,
        )
        
        if publish_event:
            publish_event({
                "type": "builder_step",
                "step": "done",
                "progress": 100,
                "path": session_path,
                "session_id": session_id,
                "message": f"Successfully generated {len(files)} files."
            })
            
        return result

    except Exception as e:
        logger.error(f"[Builder Engine] Build failed: {e}", exc_info=True)
        if publish_event:
            publish_event({"type": "error", "message": str(e)})
        return BuildResult(session_id="", output_path="", files={}, error=str(e))


def _generate_readme(prefs: Dict[str, Any], site_type: str, needs_backend: bool) -> str:
    """Generate a README.md with instructions for running the project."""
    project_title = f"{prefs.get('design', '').title()} {site_type.title()} Project"
    
    readme = f"""# {project_title}

Generated by **DreamAgent Builder** 🚀

## Quick Start

### Static Site (HTML/CSS/JS)
```bash
# Option 1: Open directly
open index.html

# Option 2: Use a local server
python -m http.server 8080
# Then visit http://localhost:8080

# Option 3: Use Node.js
npx serve .
```
"""
    if needs_backend:
        readme += """
### Backend (Python/FastAPI)
```bash
pip install fastapi uvicorn sqlalchemy
cd backend
uvicorn app:app --reload --port 8000
```

### Full Stack
```bash
# Terminal 1 — Backend
cd backend && uvicorn app:app --reload --port 8000

# Terminal 2 — Frontend
python -m http.server 8080
```
"""
    readme += f"""
## Project Info
- **Design:** {prefs.get('design', '')}
- **Type:** {site_type}
- **Backend:** {'Yes' if needs_backend else 'No (static)'}
- **Generated:** Auto-scaffolded by DreamAgent

## Editing
You can continue editing this project through the DreamAgent chat interface.
Every change creates a new version — you can always rollback.
"""
    return readme
