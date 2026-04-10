"""
backend/builder/multi_agent_builder.py

Multi-Agent Builder Pipeline:
  1. Planner Agent  — breaks down the build request into a structured spec
  2. Coder Agent    — generates the actual code files
  3. Tester Agent   — runs heuristic checks against all files
  4. Fixer Agent    — surgical fixes ONLY for failing files (max 2 attempts)
  5. Reviewer Agent — final validation + LLM auto-fix for critical issues

All agents use the same UniversalProvider so any LLM backend works.
"""

import logging
import json
import re
from typing import Dict, Any, Callable, Optional, List, Tuple

logger = logging.getLogger(__name__)

MAX_FIX_ATTEMPTS = 2

# ── SSE Progress Map ─────────────────────────────────────────────────────────
PROGRESS_MAP = {
    "planning": 10,
    "coding": 30,
    "testing": 50,
    "fixing": 70,
    "review": 90,
    "done": 100,
}


# ─── Base Agent ───────────────────────────────────────────────────────────────

class BuilderAgent:
    def __init__(self, name: str, provider: str = "auto", model: str = ""):
        self.name = name
        self.provider = provider
        self.model = model
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            from backend.llm.universal_provider import UniversalProvider
            self._llm = UniversalProvider(provider=self.provider, model=self.model)
        return self._llm

    def _call(self, messages: list) -> str:
        try:
            return self.llm.generate(messages)
        except Exception as e:
            logger.error(f"[{self.name}] LLM call failed: {e}")
            raise


# ─── Planner Agent ────────────────────────────────────────────────────────────

class PlannerAgent(BuilderAgent):
    """Converts a natural language request into a structured build spec."""

    def plan(self, user_request: str, prefs: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""You are a Senior Web Architect (Planner Agent).

The user wants to build: "{user_request}"

Parsed preferences:
- Type: {prefs.get("type", "landing")}
- Design: {prefs.get("design", "modern")}
- Backend: {prefs.get("backend", False)}
- Features: {prefs.get("features", {})}

Return ONLY a valid JSON object with this schema (no explanation, no markdown):
{{
  "project_name": "Short descriptive project name",
  "files_to_generate": ["index.html", "style.css", "app.js"],
  "sections": ["Hero", "Features", "Pricing", "Footer"],
  "color_palette": ["#primary_hex", "#secondary_hex", "#bg_hex"],
  "font": "Google Font name",
  "key_features": ["list", "of", "main", "features"]
}}
"""
        try:
            raw = self._call([{"role": "user", "content": prompt}])
            raw = raw.strip().strip("```json").strip("```").strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"[Planner] Failed to parse JSON, using defaults: {e}")
            return {
                "project_name": prefs.get("type", "web").title() + " Project",
                "files_to_generate": ["index.html", "style.css"],
                "sections": ["Hero", "Features", "Footer"],
                "color_palette": ["#00f0ff", "#8b5cf6", "#0a0a12"],
                "font": "Inter",
                "key_features": []
            }


# ─── Coder Agent ──────────────────────────────────────────────────────────────

class CoderAgent(BuilderAgent):
    """Generates actual code files based on the Planner's spec."""

    def generate(
        self,
        spec: Dict[str, Any],
        prefs: Dict[str, Any],
        publish_event: Optional[Callable] = None
    ) -> Dict[str, str]:
        """Returns {filename: content} for all files in the spec."""

        files = {}
        files_to_gen = spec.get("files_to_generate", ["index.html"])

        for i, fname in enumerate(files_to_gen):
            if publish_event:
                publish_event({
                    "type": "builder_step",
                    "step": "coding",
                    "progress": int(PROGRESS_MAP["coding"] + (i / len(files_to_gen)) * 20),
                    "message": f"Generating {fname}..."
                })

            content = self._generate_file(fname, spec, prefs, files)
            if content:
                files[fname] = content

        return files

    def _generate_file(
        self,
        filename: str,
        spec: Dict[str, Any],
        prefs: Dict[str, Any],
        already_generated: Dict[str, str]
    ) -> str:
        ext = filename.split(".")[-1]

        context = ""
        if already_generated:
            for k, v in list(already_generated.items())[:2]:
                context += f"\n--- Already generated: {k} ---\n{v[:2000]}\n"

        prompt = f"""You are an expert Web Developer (Coder Agent).

Generate the file: {filename}

Project spec:
- Name: {spec.get("project_name")}
- Sections: {", ".join(spec.get("sections", []))}
- Color palette: {spec.get("color_palette")}
- Font: {spec.get("font", "Inter")}
- Key features: {spec.get("key_features", [])}
- Design style: {prefs.get("design", "modern")}
- Type: {prefs.get("type", "landing")}
{context}

RULES:
1. Output ONLY the raw file content — no explanation, no markdown fences
2. Make it production-quality, visually impressive, fully functional
3. Use the color palette and font from the spec
4. Include all sections specified
5. Add Google Fonts import if this is a CSS/HTML file

Generate {filename}:"""

        try:
            result = self._call([{"role": "user", "content": prompt}])
            result = result.strip()
            fences = [f"```{ext}", "```html", "```css", "```js", "```"]
            for fence in fences:
                if result.startswith(fence):
                    result = result[len(fence):]
                    break
            if result.endswith("```"):
                result = result[:-3]
            return result.strip()
        except Exception as e:
            logger.error(f"[Coder] Failed to generate {filename}: {e}")
            return ""


# ─── Tester Agent (Heuristic) ─────────────────────────────────────────────────

class TesterAgent(BuilderAgent):
    """Runs comprehensive heuristic checks against all generated files."""

    def test(self, files: Dict[str, str], spec: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Returns {filename: [list_of_issues]} for files with problems.
        Empty dict = all passed.
        """
        results: Dict[str, List[str]] = {}

        for fname, content in files.items():
            issues = self._test_file(fname, content, spec)
            if issues:
                results[fname] = issues

        return results

    def _test_file(self, filename: str, content: str, spec: Dict[str, Any]) -> List[str]:
        issues = []
        ext = filename.split(".")[-1]

        if not content.strip():
            issues.append("File is empty")
            return issues

        if ext in ("html", "htm"):
            low = content.lower()

            # Structure checks
            if "<html" not in low:
                issues.append("Missing <html> tag")
            if "<head" not in low:
                issues.append("Missing <head> section")
            if "<body" not in low:
                issues.append("Missing <body> section")
            if "<title" not in low:
                issues.append("Missing <title> tag")
            if 'viewport' not in low:
                issues.append("Missing <meta viewport> for mobile responsiveness")

            # Empty body check
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            if body_match and len(body_match.group(1).strip()) < 10:
                issues.append("Empty <body> — no visible content")

            # Broken link/script references
            for tag in re.findall(r'<(?:link|script)[^>]*(?:href|src)="([^"]*)"', content, re.IGNORECASE):
                if tag.startswith("http"):
                    continue  # External — fine
                if not any(tag.endswith(e) for e in (".css", ".js", ".ico", ".png", ".jpg", ".svg", ".woff2")):
                    if tag and not tag.startswith("#") and not tag.startswith("data:"):
                        issues.append(f"Suspicious local reference: {tag}")

            # Section checks
            for section in spec.get("sections", []):
                if section.lower() not in content.lower():
                    issues.append(f"Missing section: {section}")

        elif ext == "css":
            if content.count("{") != content.count("}"):
                issues.append("Unbalanced curly braces in CSS")

        elif ext in ("js", "ts", "jsx", "tsx"):
            if content.count("{") != content.count("}"):
                issues.append("Unbalanced curly braces in JS")
            if content.count("(") != content.count(")"):
                issues.append("Unbalanced parentheses in JS")

        return issues


# ─── Fixer Agent ──────────────────────────────────────────────────────────────

class FixerAgent(BuilderAgent):
    """Surgically fixes ONLY the files that failed testing. Scope-locked."""

    def fix(
        self,
        failed_files: Dict[str, List[str]],
        all_files: Dict[str, str],
        spec: Dict[str, Any],
        publish_event: Optional[Callable] = None,
    ) -> Tuple[Dict[str, str], int]:
        """
        Attempts to fix only the failing files. Returns (fixed_files, attempt_count).
        Obeys MAX_FIX_ATTEMPTS to prevent infinite loops.
        """
        attempt = 0
        current_failures = dict(failed_files)
        working_files = dict(all_files)

        while current_failures and attempt < MAX_FIX_ATTEMPTS:
            attempt += 1
            logger.info(f"[Fixer] Attempt {attempt}/{MAX_FIX_ATTEMPTS} — fixing {len(current_failures)} file(s)")

            if publish_event:
                publish_event({
                    "type": "builder_step",
                    "step": "fixing",
                    "progress": PROGRESS_MAP["fixing"] + (attempt / MAX_FIX_ATTEMPTS) * 10,
                    "message": f"Fix attempt {attempt}/{MAX_FIX_ATTEMPTS}: repairing {', '.join(current_failures.keys())}..."
                })

            for fname, issues in list(current_failures.items()):
                fixed_content = self._fix_file(fname, working_files[fname], issues, spec)
                if fixed_content:
                    working_files[fname] = fixed_content

            # Re-test only the previously failing files
            tester = TesterAgent("Tester-Recheck")
            subset = {k: working_files[k] for k in current_failures if k in working_files}
            current_failures = tester.test(subset, spec)

        if current_failures:
            logger.warning(f"[Fixer] Exceeded {MAX_FIX_ATTEMPTS} attempts. Remaining issues: {current_failures}")

        return working_files, attempt

    def _fix_file(self, filename: str, content: str, issues: List[str], spec: Dict[str, Any]) -> str:
        issues_str = "\n".join(f"- {i}" for i in issues)
        prompt = f"""You are a Code Fixer repairing specific bugs in a generated file.

File: {filename}
Issues to fix:
{issues_str}

Current content:
{content[:10000]}

RULES:
1. Fix ONLY the listed issues — do NOT rewrite the entire file
2. Keep all existing functionality intact
3. Output ONLY the corrected file content — no explanation, no markdown fences

Fixed {filename}:"""

        try:
            result = self._call([{"role": "user", "content": prompt}])
            result = result.strip()
            # Strip markdown fences
            for fence in ["```html", "```css", "```js", "```"]:
                if result.startswith(fence):
                    result = result[len(fence):]
                    break
            if result.endswith("```"):
                result = result[:-3]
            return result.strip()
        except Exception as e:
            logger.error(f"[Fixer] Failed to fix {filename}: {e}")
            return ""


# ─── Reviewer Agent ───────────────────────────────────────────────────────────

class ReviewerAgent(BuilderAgent):
    """Final review pass — catches anything the Tester/Fixer missed."""

    def review(self, files: Dict[str, str], spec: Dict[str, Any]) -> Dict[str, Any]:
        issues = []
        fixed_files = {}

        for fname, content in files.items():
            file_issues = self._review_file(fname, content, spec)
            if file_issues:
                issues.extend([f"{fname}: {i}" for i in file_issues])
                if any("missing" in i.lower() or "broken" in i.lower() for i in file_issues):
                    fixed = self._auto_fix(fname, content, file_issues, spec)
                    if fixed:
                        fixed_files[fname] = fixed

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "fixed_files": fixed_files
        }

    def _review_file(self, filename: str, content: str, spec: Dict[str, Any]) -> list:
        issues = []
        ext = filename.split(".")[-1]

        if not content.strip():
            issues.append("File is empty")
            return issues

        if ext in ("html", "htm"):
            low = content.lower()
            if "<html" not in low:
                issues.append("Missing <html> tag")
            if "<head" not in low:
                issues.append("Missing <head> section")
            if "<body" not in low:
                issues.append("Missing <body> section")

        elif ext == "css":
            if content.count("{") != content.count("}"):
                issues.append("Broken CSS: unbalanced curly braces")

        elif ext in ("js", "ts"):
            if content.count("{") != content.count("}"):
                issues.append("Broken JS: unbalanced curly braces")

        return issues

    def _auto_fix(self, filename: str, content: str, issues: list, spec: Dict[str, Any]) -> str:
        issues_str = "\n".join(f"- {i}" for i in issues)
        prompt = f"""You are a Code Reviewer fixing bugs in a generated file.

File: {filename}
Issues found:
{issues_str}

Current content:
{content[:10000]}

Fix ALL the listed issues. Output ONLY the corrected file content — no explanation."""

        try:
            result = self._call([{"role": "user", "content": prompt}])
            return result.strip().strip("```").strip()
        except Exception as e:
            logger.error(f"[Reviewer] Auto-fix failed for {filename}: {e}")
            return ""


# ─── Orchestrator ─────────────────────────────────────────────────────────────

async def multi_agent_build(
    user_request: str,
    prefs: Dict[str, Any],
    provider: str = "auto",
    model: str = "",
    publish_event: Optional[Callable] = None
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Runs the full Planner → Coder → Tester → Fixer → Reviewer pipeline.
    Returns (final_files, spec) tuple.
    """
    fix_attempts_used = 0

    def emit(step: str, progress: int, message: str):
        if publish_event:
            publish_event({"type": "builder_step", "step": step, "progress": progress, "message": message})
        logger.info(f"[MultiAgent] [{step}] {message}")

    # ── 1. PLANNER ────────────────────────────────────────────────
    emit("planning", PROGRESS_MAP["planning"], "🧠 Planner analyzing your request...")

    planner = PlannerAgent("Planner", provider=provider, model=model)
    spec = planner.plan(user_request, prefs)
    logger.info(f"[MultiAgent] Spec: {spec}")

    # ── 2. CODER ──────────────────────────────────────────────────
    emit("coding", PROGRESS_MAP["coding"], f"⚙️ Coder generating {len(spec.get('files_to_generate', []))} files...")

    coder = CoderAgent("Coder", provider=provider, model=model)
    files = coder.generate(spec, prefs, publish_event=publish_event)

    if not files:
        emit("error", 0, "Coder generated no files")
        return {}, spec

    # ── 3. TESTER ─────────────────────────────────────────────────
    emit("testing", PROGRESS_MAP["testing"], "🧪 Tester running heuristic checks...")

    tester = TesterAgent("Tester", provider=provider, model=model)
    test_results = tester.test(files, spec)

    if test_results:
        logger.info(f"[MultiAgent] Tester found issues in {len(test_results)} file(s)")

        # ── 4. FIXER (max 2 attempts) ─────────────────────────────
        emit("fixing", PROGRESS_MAP["fixing"], f"🔧 Fixer repairing {len(test_results)} file(s)...")

        fixer = FixerAgent("Fixer", provider=provider, model=model)
        files, fix_attempts_used = fixer.fix(test_results, files, spec, publish_event=publish_event)
    else:
        logger.info("[MultiAgent] Tester passed — all files clean")

    # ── 5. REVIEWER ───────────────────────────────────────────────
    emit("review", PROGRESS_MAP["review"], "🔍 Reviewer performing final pass...")

    reviewer = ReviewerAgent("Reviewer", provider=provider, model=model)
    review = reviewer.review(files, spec)

    if review.get("fixed_files"):
        files.update(review["fixed_files"])
        emit("review", 95, f"✅ Reviewer applied {len(review['fixed_files'])} final fix(es)")

    if review.get("issues") and not review["passed"]:
        logger.warning(f"[MultiAgent] Residual review issues: {review['issues']}")

    emit("done", PROGRESS_MAP["done"], "🚀 Multi-agent build complete!")

    # Record telemetry
    try:
        from backend.builder.telemetry import record_event
        record_event("pipeline", "update_success", fix_attempts=fix_attempts_used)
    except Exception:
        pass

    return files, spec
