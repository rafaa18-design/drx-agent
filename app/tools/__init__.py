"""Custom tools for the agent.

Add your custom tools here. Each tool should be decorated with @tool.
"""

from agno.tools import tool


@tool
def get_current_time() -> str:
    """Get the current date and time in ISO format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")

    Returns:
        The result of the calculation as a string.
    """
    import ast
    import operator

    allowed_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def eval_expr(node: ast.expr) -> float:
        if isinstance(node, ast.Constant):
            return float(node.value)
        elif isinstance(node, ast.BinOp):
            left = eval_expr(node.left)
            right = eval_expr(node.right)
            op = allowed_operators.get(type(node.op))
            if op is None:
                raise ValueError(
                    f'Unsupported operator: {type(node.op).__name__}'
                )
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = eval_expr(node.operand)
            op = allowed_operators.get(type(node.op))
            if op is None:
                raise ValueError(
                    f'Unsupported operator: {type(node.op).__name__}'
                )
            return op(operand)
        else:
            raise ValueError(
                f'Unsupported expression type: {type(node).__name__}'
            )

    try:
        tree = ast.parse(expression, mode='eval')
        result = eval_expr(tree.body)
        return str(result)
    except Exception as e:
        return f'Error: {e}'


# Export all tools
__all__ = ['get_current_time', 'calculate']
