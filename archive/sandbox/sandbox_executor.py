"""
sandbox/sandbox_executor.py
Subprocess-based code execution with AST-level safety validation.

Replaces the previous string-match filter (easily bypassed) with the
SafetyGuard AST checker.  The subprocess also runs with an empty
environment to prevent secret leakage via inherited env vars.

For production use, prefer SANDBOX_MODE=docker (DockerRunner) which adds
network and filesystem isolation on top of this.
"""

import os
import sys
import logging
import tempfile
import subprocess

logger = logging.getLogger(__name__)

# Minimum safe environment for the subprocess — no inherited secrets.
_SAFE_ENV = {
    "PYTHONPATH": os.getcwd(),
    "PATH": "/usr/local/bin:/usr/bin:/bin",
}


def run_code_safely(code: str, timeout: int = 5) -> str:
    """
    Validate then execute Python code in a restricted subprocess.

    Validation uses the AST-based SafetyGuard (two-pass: regex + AST walk).
    String-matching is NOT used as the primary filter — it is trivially
    bypassed with whitespace, getattr, or encoded payloads.

    Args:
        code:    Python source code to execute.
        timeout: Maximum wall-clock seconds; default 5.

    Returns:
        Stdout of the executed code, or an error/security message string.
    """
    # --- Pass 1: AST-based static analysis ---
    from sandbox.safety_guard import SafetyGuard
    guard = SafetyGuard()
    is_safe, violations = guard.validate_code(code)
    if not is_safe:
        logger.warning("run_code_safely: code rejected. Violations: %s", violations)
        return "Security Blocked: " + "; ".join(violations)

    # --- Pass 2: execute in isolated subprocess ---
    fname = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".py", mode="w", encoding="utf-8"
        ) as f:
            f.write(code)
            fname = f.name

        result = subprocess.run(
            [sys.executable, fname],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_SAFE_ENV,   # no inherited environment — no secrets leak
        )
        output = result.stdout
        if result.stderr:
            output += "\nErrors:\n" + result.stderr
        return output

    except subprocess.TimeoutExpired:
        logger.warning("run_code_safely: execution timed out after %ds.", timeout)
        return f"Execution Error: Code timed out after {timeout} seconds."
    except Exception as e:
        logger.error("run_code_safely: unexpected error: %s", e)
        return f"Execution Error: {e}"
    finally:
        if fname and os.path.exists(fname):
            try:
                os.remove(fname)
            except OSError as e:
                logger.warning("run_code_safely: could not remove temp file: %s", e)
