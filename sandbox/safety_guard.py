"""
sandbox/safety_guard.py

Advanced AST and Regex-based code validation for the python sandbox.
"""

import ast
import re
from typing import Tuple, List

# Core regex rules
FORBIDDEN_PATTERNS = [
    r"__import__", r"eval\(", r"exec\(", r"open\(",
]

FORBIDDEN_IMPORTS = {"os", "sys", "subprocess", "shutil", "socket", "pty"}

class SafetyGuard:
    def __init__(self):
        pass

    def validate_code(self, code: str) -> Tuple[bool, List[str]]:
        """
        Validates the provided python code using Regex and AST parsing.
        Returns:
            is_safe: bool
            violations: list of violation strings if not safe
        """
        violations = []
        
        # 1. Regex checks for low-level function calls
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, code):
                violations.append(f"Forbidden pattern detected: {pattern}")

        # 2. Advanced AST traversal
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Check for restricted imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in FORBIDDEN_IMPORTS:
                            violations.append(f"Forbidden import: {alias.name}")
                            
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] in FORBIDDEN_IMPORTS:
                        violations.append(f"Forbidden from-import: {node.module}")
                        
                # Check for restricted functions
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['open', 'eval', 'exec', '__import__', 'globals', 'locals']:
                            violations.append(f"Forbidden function call: {node.func.id}")
                            
        except SyntaxError as e:
            violations.append(f"SyntaxError: {str(e)}")
            
        return len(violations) == 0, violations
