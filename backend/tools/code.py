"""
backend/tools/code.py (Hardened v2)
Fix #14: Code is now validated through sandbox/SafetyGuard (AST + regex) before execution.
"""
import re
import subprocess
import sys
import os
import logging

logger = logging.getLogger(__name__)

# Try to use the advanced sandbox SafetyGuard from sandbox/
try:
    _sandbox_path = os.path.join(os.path.dirname(__file__), '..', '..', 'sandbox')
    if _sandbox_path not in sys.path:
        sys.path.insert(0, _sandbox_path)
    from safety_guard import SafetyGuard
    _guard = SafetyGuard()
    _USE_SANDBOX_GUARD = True
    logger.info("[code.py] Using sandbox SafetyGuard (AST + regex validation)")
except Exception as e:
    _guard = None
    _USE_SANDBOX_GUARD = False
    logger.warning(f"[code.py] sandbox SafetyGuard unavailable ({e}). Using basic blocklist.")

# Fallback basic blocklist
_BASIC_BLOCKED = [
    r"\bos\b", r"\bsubprocess\b", r"\bshutil\b", r"\bsocket\b",
    r"__import__", r"\beval\b", r"\bexec\b", r"\bopen\b",
    r"import\s+sys", r"import\s+os", r"import\s+subprocess",
    r"from\s+os\b", r"from\s+subprocess\b",
]


class CodeTool:
    def run(self, code: str) -> str:
        if len(code) > 2000:
            return "Blocked: Code exceeds 2000 character limit"

        if _USE_SANDBOX_GUARD and _guard:
            # Use advanced AST + regex validation from sandbox
            is_safe, violations = _guard.validate_code(code)
            if not is_safe:
                return f"Blocked: {'; '.join(violations[:3])}"
        else:
            # Basic fallback pattern check
            for pattern in _BASIC_BLOCKED:
                if re.search(pattern, code, re.IGNORECASE):
                    return f"Blocked: Code contains restricted operation ('{pattern}')"

        try:
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                timeout=5,
                text=True,
                env={"PYTHONPATH": ""},  # Isolated environment
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                return output[:1000] if output else "Code executed successfully (no output)"
            else:
                return f"Execution error: {result.stderr.strip()[:500]}"
        except subprocess.TimeoutExpired:
            return "Blocked: Code execution timed out (5s limit)"
        except Exception as e:
            return f"Execution error: {str(e)}"
