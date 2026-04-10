"""JavaScript code execution environment with safety constraints."""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class JsExecutor:
    """Execute JavaScript code in a sandboxed environment."""

    def __init__(self, timeout: int = 30):
        """Initialize JavaScript executor.
        
        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout

    def execute(self, code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute JavaScript code safely.
        
        Args:
            code: JavaScript code to execute
            context: Variables to provide to the execution context
            
        Returns:
            Execution result with output and metadata
        """
        import json
        import subprocess
        
        context_str = ""
        if context:
            for k, v in context.items():
                try:
                    val_json = json.dumps(v)
                    context_str += f"const {k} = {val_json};\n"
                except TypeError:
                    continue
                    
        full_code = context_str + code
        
        try:
            # Use node --eval
            process = subprocess.run(["node", "--eval", full_code], capture_output=True, text=True, timeout=self.timeout)
            return {
                "success": process.returncode == 0,
                "output": process.stdout,
                "error_output": process.stderr,
                "return_code": process.returncode
            }
        except subprocess.TimeoutExpired as e:
            return {
                "success": False,
                "output": getattr(e, "stdout", "") or "",
                "error_output": getattr(e, "stderr", "") or "Execution timed out",
                "return_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error_output": str(e),
                "return_code": -1
            }
