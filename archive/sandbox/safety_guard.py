"""Safety guards for code execution in sandboxed environments."""

from typing import List, Tuple
import logging
import ast
import re

logger = logging.getLogger(__name__)


class SafetyGuard:
    """Enforce safety constraints during code execution."""

    def __init__(self):
        """Initialize safety guard with default policies."""
        self.blocked_imports = {"os", "sys", "subprocess", "socket", "ctypes", "pty", "shutil", "urllib", "requests"}
        self.blocked_functions = {"eval", "exec", "open", "compile", "globals", "locals", "__import__"}
        
        # Patterns for regex pass
        self.dangerous_patterns = [
            r"os\.system", r"subprocess\.", r"socket\.", r"ctypes\.", 
            r"open\(", r"__import__", r"eval\(", r"exec\(", r"globals\(", r"locals\("
        ]

    def validate_code(self, code: str) -> Tuple[bool, List[str]]:
        """Validate code for unsafe operations.
        
        Args:
            code: Code to validate
            
        Returns:
            Tuple of (is_safe, violations)
        """
        violations = []
        
        # Pass 1: Regex
        for pattern in self.dangerous_patterns:
            if re.search(pattern, code):
                violations.append(f"Code contains blocked pattern matching regex: {pattern}")
                
        # Pass 2: AST traversal
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in self.blocked_imports:
                            violations.append(f"Blocked import detected: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    mod_name = getattr(node, "module", None)
                    if mod_name and isinstance(mod_name, str) and mod_name.split('.')[0] in self.blocked_imports:
                        violations.append(f"Blocked import detected: {mod_name}")
                elif isinstance(node, ast.Call):
                    func = getattr(node, "func", None)
                    if isinstance(func, ast.Name):
                        func_id = getattr(func, "id", "")
                        if func_id in self.blocked_functions:
                            violations.append(f"Blocked function call detected: {func_id}")
                    elif isinstance(func, ast.Attribute):
                        val = getattr(func, "value", None)
                        if isinstance(val, ast.Name):
                            val_id = getattr(val, "id", "")
                            attr_name = getattr(func, "attr", "")
                            # Catch os.system style calls if they bypassed the import check
                            if val_id in self.blocked_imports:
                                violations.append(f"Method call on blocked module detected: {val_id}.{attr_name}")
        except SyntaxError as e:
            violations.append(f"Syntax error in code: {e}")
            
        is_safe = len(violations) == 0
        if not is_safe:
            logger.warning(f"Code validation failed. Violations: {violations}")
            
        return is_safe, violations

    def add_blocked_import(self, module: str) -> None:
        """Add a module to the blocked imports list."""
        self.blocked_imports.add(module)

    def add_blocked_function(self, function: str) -> None:
        """Add a function to the blocked functions list."""
        self.blocked_functions.add(function)
