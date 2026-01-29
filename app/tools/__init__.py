"""Custom tools for the agent.

Add your custom tools here. Each tool should be decorated with @tool.

This module demonstrates proper use of Agno exceptions:
- RetryAgentRun: Provides feedback to the model to adjust behavior and retry
- StopAgentRun: Stops the tool call loop immediately
"""

from agno.exceptions import RetryAgentRun, StopAgentRun
from agno.run import RunContext
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
        ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv,
    }

    def eval_expr(node: ast.expr) -> float:
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise RetryAgentRun(
                    f'Unsupported constant type: {type(node.value).__name__}. '
                    'Please use only numbers in the expression.'
                )
            return float(node.value)
        elif isinstance(node, ast.BinOp):
            left = eval_expr(node.left)
            right = eval_expr(node.right)
            op = allowed_operators.get(type(node.op))
            if op is None:
                raise RetryAgentRun(
                    f'Unsupported operator: {type(node.op).__name__}. '
                    'Supported operators: +, -, *, /, **, %, //'
                )
            return float(op(left, right))
        elif isinstance(node, ast.UnaryOp):
            operand = eval_expr(node.operand)
            op = allowed_operators.get(type(node.op))
            if op is None:
                raise RetryAgentRun(
                    f'Unsupported operator: {type(node.op).__name__}. '
                    'Supported operators: +, -, *, /, **, %, //'
                )
            return float(op(operand))
        else:
            raise RetryAgentRun(
                f'Unsupported expression type: {type(node).__name__}. '
                'Please provide a simple mathematical expression like "2 + 2" or "10 * 5".'
            )

    try:
        tree = ast.parse(expression, mode='eval')
        result = eval_expr(tree.body)
        # Return integer if possible
        if result == int(result):
            return str(int(result))
        return str(result)
    except RetryAgentRun:
        raise  # Re-raise RetryAgentRun exceptions
    except SyntaxError:
        raise RetryAgentRun(
            f'Invalid expression syntax: "{expression}". '
            'Please provide a valid mathematical expression like "2 + 2" or "10 * 5".'
        )
    except ZeroDivisionError:
        raise RetryAgentRun(
            'Division by zero is not allowed. Please provide a different expression.'
        )
    except Exception as e:
        raise RetryAgentRun(
            f'Error evaluating expression: {e}. '
            'Please provide a simple mathematical expression.'
        )


@tool
def generate_uuid() -> str:
    """Generate a unique identifier (UUID4).

    Useful for creating unique IDs for resources, transactions, or tracking.

    Returns:
        A new UUID4 string.
    """
    from uuid import uuid4

    return str(uuid4())


@tool
def format_date(date_string: str, output_format: str = '%Y-%m-%d') -> str:
    """Format a date string to a different format.

    Args:
        date_string: The date string to format (various formats supported)
        output_format: The desired output format (default: YYYY-MM-DD)

    Returns:
        The formatted date string.
    """
    from datetime import datetime

    common_formats = [
        '%Y-%m-%d',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%d-%m-%Y',
        '%B %d, %Y',
        '%b %d, %Y',
    ]

    for fmt in common_formats:
        try:
            parsed = datetime.strptime(date_string.strip(), fmt)
            return parsed.strftime(output_format)
        except ValueError:
            continue

    # Use RetryAgentRun to give feedback to the model
    raise RetryAgentRun(
        f'Could not parse date "{date_string}". '
        f'Supported formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, ISO 8601. '
        'Please provide the date in one of these formats.'
    )


# ============================================================================
# Example tools demonstrating session state with RetryAgentRun
# ============================================================================


@tool
def add_to_list(
    run_context: RunContext, item: str, list_name: str = 'items'
) -> str:
    """Add an item to a named list in session state.

    This tool demonstrates using RetryAgentRun with session state.
    The list requires at least 3 items before it's considered complete.

    Args:
        item: The item to add to the list.
        list_name: Name of the list (default: "items").

    Returns:
        Current state of the list.
    """
    # Initialize session state if needed
    if not run_context.session_state:
        run_context.session_state = {}

    if list_name not in run_context.session_state:
        run_context.session_state[list_name] = []

    # Add item to list
    run_context.session_state[list_name].append(item)
    current_list = run_context.session_state[list_name]
    list_length = len(current_list)

    # Require minimum 3 items - demonstrates RetryAgentRun usage
    if list_length < 3:
        raise RetryAgentRun(
            f'List "{list_name}" has {list_length} items: {current_list}. '
            f'Minimum 3 items required. Please add {3 - list_length} more items.'
        )

    return f'List "{list_name}" is complete with {list_length} items: {current_list}'


@tool
def check_threshold(
    run_context: RunContext, value: int, threshold: int = 100
) -> str:
    """Check if a value exceeds a threshold.

    This tool demonstrates using StopAgentRun to stop execution
    when a critical condition is met.

    Args:
        value: The value to check.
        threshold: Maximum allowed value (default: 100).

    Returns:
        Confirmation that the value is within the threshold.
    """
    if value > threshold:
        # StopAgentRun immediately stops the tool call loop
        raise StopAgentRun(
            f'Value {value} exceeds threshold of {threshold}. '
            'Stopping execution to prevent invalid operations.'
        )

    return f'Value {value} is within the acceptable threshold of {threshold}.'


# Export all tools
__all__ = [
    'get_current_time',
    'calculate',
    'generate_uuid',
    'format_date',
    'add_to_list',
    'check_threshold',
]
