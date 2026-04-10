"""Safe calculator tool — replaces raw eval() with AST whitelist to eliminate RCE risk."""

import ast
import re
import operator

# Allowed AST node types for safe math evaluation
_SAFE_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Num,        # Python < 3.8 literal numbers
    ast.Constant,   # Python >= 3.8 literals
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    ast.Pow, ast.FloorDiv,
    ast.UAdd, ast.USub,
)

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    """Recursively evaluate a whitelisted AST node."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Num):  # legacy Python < 3.8
        return node.n
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        return _SAFE_OPS[op_type](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _SAFE_OPS[op_type](_safe_eval(node.operand))
    raise ValueError(f"Unsafe node type: {type(node).__name__}")


def calculate(expression: str) -> str:
    """
    Safely evaluate a mathematical expression string.

    Uses AST parsing with a strict node whitelist — no arbitrary code execution.

    Args:
        expression: A math expression string, e.g. "2 + 3 * 4".
                    May also be a natural-language message containing math (e.g. "what is 10 / 2?").

    Returns:
        The result as a string, or an error message.
    """
    # If expression looks like a natural-language message, extract a math substring
    if not re.fullmatch(r"[\d\s+\-*/^().%]+", expression.strip()):
        candidates = re.findall(r"[\d+\-*/.^()%\s]+", expression)
        if not candidates:
            return "No math expression found"
        expression = max(candidates, key=len).strip()

    if not expression:
        return "No math expression found"

    try:
        tree = ast.parse(expression, mode="eval")
        # Ensure every node in the tree is whitelisted
        for node in ast.walk(tree):
            if not isinstance(node, _SAFE_NODES):
                return f"Unsafe expression — disallowed construct: {type(node).__name__}"
        result = _safe_eval(tree)
        # Guard against unusably large numbers
        if isinstance(result, float) and (result != result or result == float("inf") or result == float("-inf")):
            return "Calculation error: result is not finite"
        return str(result)
    except ZeroDivisionError:
        return "Calculation error: division by zero"
    except Exception as e:
        return f"Calculation error: {e}"