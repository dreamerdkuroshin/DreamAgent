"""Python code execution environment with safety constraints."""

from typing import Dict, Any, Optional
import logging
import sys
import io
import threading
import time

from sandbox.safety_guard import SafetyGuard

logger = logging.getLogger(__name__)


class PythonExecutor:
    """Execute Python code in a sandboxed environment."""

    def __init__(self, timeout: int = 30):
        """Initialize Python executor.
        
        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout
        self.safety_guard = SafetyGuard()

    def execute(self, code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute Python code safely using a subprocess."""
        from sandbox.sandbox_executor import run_code_safely
        
        is_safe, violations = self.safety_guard.validate_code(code)
        if not is_safe:
            return {"success": False, "error": "Safety violation", "violations": violations}
            
        import os
        if os.getenv("SANDBOX_MODE") == "docker":
            from sandbox.docker_runner import DockerRunner
            output = DockerRunner().run(code, timeout=self.timeout)
        else:
            output = run_code_safely(code, timeout=self.timeout)

        
        if "Execution Error" in output or "Security Blocked" in output:
            return {"success": False, "output": output}
            
        return {"success": True, "output": output}
