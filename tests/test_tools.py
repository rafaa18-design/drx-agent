"""Tests for custom tools demonstrating Agno exceptions."""

import pytest
from agno.exceptions import RetryAgentRun, StopAgentRun
from agno.run import RunContext

# Import the tool wrappers and access the underlying functions
from app.tools import (add_to_list, calculate, check_threshold, format_date,
                       generate_uuid, get_current_time)


# Helper to get the actual callable function from Agno Function wrapper
def call_tool(tool_func, *args, **kwargs):
    """Call a tool function, handling Agno Function wrapper."""
    if hasattr(tool_func, 'func'):
        # Agno Function wrapper - call the underlying function
        return tool_func.func(*args, **kwargs)
    elif hasattr(tool_func, 'entrypoint'):
        # Alternative wrapper structure
        return tool_func.entrypoint(*args, **kwargs)
    else:
        # Direct function
        return tool_func(*args, **kwargs)


class TestBasicTools:
    """Tests for basic utility tools."""

    def test_get_current_time(self):
        """Test get_current_time returns ISO format."""
        result = call_tool(get_current_time)
        assert isinstance(result, str)
        assert 'T' in result  # ISO format has T separator
        assert result.endswith('+00:00') or result.endswith('Z')

    def test_generate_uuid(self):
        """Test generate_uuid returns valid UUID."""
        result = call_tool(generate_uuid)
        assert isinstance(result, str)
        assert len(result) == 36  # UUID format: 8-4-4-4-12
        assert result.count('-') == 4

    def test_generate_uuid_unique(self):
        """Test generate_uuid returns unique values."""
        uuids = [call_tool(generate_uuid) for _ in range(10)]
        assert len(set(uuids)) == 10  # All unique


class TestCalculateTool:
    """Tests for calculate tool with RetryAgentRun exceptions."""

    def test_calculate_simple_addition(self):
        """Test simple addition."""
        assert call_tool(calculate, '2 + 2') == '4'

    def test_calculate_multiplication(self):
        """Test multiplication."""
        assert call_tool(calculate, '10 * 5') == '50'

    def test_calculate_division(self):
        """Test division returns float when needed."""
        assert call_tool(calculate, '10 / 4') == '2.5'

    def test_calculate_integer_division(self):
        """Test division returns integer when possible."""
        assert call_tool(calculate, '10 / 2') == '5'

    def test_calculate_complex_expression(self):
        """Test complex expression."""
        assert call_tool(calculate, '(2 + 3) * 4') == '20'

    def test_calculate_power(self):
        """Test power operator."""
        assert call_tool(calculate, '2 ** 3') == '8'

    def test_calculate_modulo(self):
        """Test modulo operator."""
        assert call_tool(calculate, '10 % 3') == '1'

    def test_calculate_floor_division(self):
        """Test floor division."""
        assert call_tool(calculate, '10 // 3') == '3'

    def test_calculate_negative(self):
        """Test negative numbers."""
        assert call_tool(calculate, '-5 + 3') == '-2'

    def test_calculate_invalid_syntax_raises_retry(self):
        """Test invalid syntax raises RetryAgentRun.

        RetryAgentRun provides feedback to the model to adjust behavior
        and retry the tool call within the current run.
        """
        with pytest.raises(RetryAgentRun) as exc_info:
            call_tool(calculate, '2 +')
        assert 'Invalid expression syntax' in str(exc_info.value)

    def test_calculate_division_by_zero_raises_retry(self):
        """Test division by zero raises RetryAgentRun.

        The model receives this error and can adjust its approach.
        """
        with pytest.raises(RetryAgentRun) as exc_info:
            call_tool(calculate, '10 / 0')
        assert 'Division by zero' in str(exc_info.value)

    def test_calculate_unsupported_operator_raises_retry(self):
        """Test unsupported operators raise RetryAgentRun."""
        # Bitwise operators are not supported
        with pytest.raises(RetryAgentRun) as exc_info:
            call_tool(calculate, '5 & 3')
        assert 'Supported operators' in str(exc_info.value)


class TestFormatDateTool:
    """Tests for format_date tool with RetryAgentRun exceptions."""

    def test_format_date_iso(self):
        """Test formatting ISO date."""
        result = call_tool(format_date, '2024-01-15')
        assert result == '2024-01-15'

    def test_format_date_with_time(self):
        """Test formatting date with time."""
        result = call_tool(format_date, '2024-01-15T10:30:00')
        assert result == '2024-01-15'

    def test_format_date_custom_output(self):
        """Test custom output format."""
        result = call_tool(format_date, '2024-01-15', '%d/%m/%Y')
        assert result == '15/01/2024'

    def test_format_date_from_slash_format(self):
        """Test parsing slash format."""
        result = call_tool(format_date, '15/01/2024')
        assert result == '2024-01-15'

    def test_format_date_with_microseconds(self):
        """Test formatting date with microseconds."""
        result = call_tool(format_date, '2024-01-15T10:30:00.123456')
        assert result == '2024-01-15'

    def test_format_date_invalid_raises_retry(self):
        """Test invalid date raises RetryAgentRun.

        RetryAgentRun gives feedback about supported formats
        so the model can provide a correctly formatted date.
        """
        with pytest.raises(RetryAgentRun) as exc_info:
            call_tool(format_date, 'not a date')
        error_msg = str(exc_info.value)
        assert 'Could not parse date' in error_msg
        assert 'Supported formats' in error_msg

    def test_format_date_partial_date_raises_retry(self):
        """Test partial date raises RetryAgentRun."""
        with pytest.raises(RetryAgentRun):
            call_tool(format_date, '2024-01')  # Missing day


class TestAgnoExceptionsDocumentation:
    """Tests documenting how Agno exceptions work.

    These tests serve as documentation for how RetryAgentRun and
    StopAgentRun should be used in tools.
    """

    def test_retry_agent_run_is_exception(self):
        """Verify RetryAgentRun is an exception that can be raised."""
        assert issubclass(RetryAgentRun, Exception)

    def test_stop_agent_run_is_exception(self):
        """Verify StopAgentRun is an exception that can be raised."""
        assert issubclass(StopAgentRun, Exception)

    def test_retry_agent_run_with_message(self):
        """Test RetryAgentRun can be created with a message."""
        exc = RetryAgentRun('Please try a different input')
        assert 'different input' in str(exc)

    def test_stop_agent_run_with_message(self):
        """Test StopAgentRun can be created with a message."""
        exc = StopAgentRun('Threshold exceeded, stopping')
        assert 'Threshold exceeded' in str(exc)

    def test_retry_vs_stop_purpose(self):
        """Document the different purposes of the exceptions.

        RetryAgentRun: Feedback to model within current run's tool call loop.
                       The model can adjust and retry.

        StopAgentRun:  Immediately exits the tool call loop.
                       The run completes with COMPLETED status.
        """
        # Both are exceptions that can be raised in tools
        retry = RetryAgentRun('Validation failed, please adjust')
        stop = StopAgentRun('Critical condition reached')

        # They carry messages for the model/user
        assert str(retry)
        assert str(stop)


def create_run_context(session_state: dict | None = None) -> RunContext:
    """Create a RunContext for testing tools.

    Args:
        session_state: Initial session state (default: None).

    Returns:
        A RunContext instance for testing.
    """
    return RunContext(
        run_id='test-run-id',
        session_id='test-session-id',
        session_state=session_state,
    )


class TestAddToListTool:
    """Tests for add_to_list tool with RunContext."""

    def test_add_to_list_initializes_state(self):
        """Test that add_to_list initializes session state if None."""
        context = create_run_context(session_state=None)

        with pytest.raises(RetryAgentRun) as exc_info:
            call_tool(add_to_list, context, 'item1')

        # Session state should now be initialized
        assert context.session_state is not None
        assert 'items' in context.session_state
        assert 'item1' in context.session_state['items']
        assert 'Minimum 3 items required' in str(exc_info.value)

    def test_add_to_list_requires_minimum_items(self):
        """Test that add_to_list requires minimum 3 items."""
        context = create_run_context(session_state={})

        # First item - should raise RetryAgentRun
        with pytest.raises(RetryAgentRun) as exc_info:
            call_tool(add_to_list, context, 'item1')
        assert '1 items' in str(exc_info.value)
        assert 'add 2 more' in str(exc_info.value)

        # Second item - should raise RetryAgentRun
        with pytest.raises(RetryAgentRun) as exc_info:
            call_tool(add_to_list, context, 'item2')
        assert '2 items' in str(exc_info.value)
        assert 'add 1 more' in str(exc_info.value)

        # Third item - should succeed
        result = call_tool(add_to_list, context, 'item3')
        assert 'complete with 3 items' in result
        assert "['item1', 'item2', 'item3']" in result

    def test_add_to_list_custom_list_name(self):
        """Test add_to_list with custom list name."""
        context = create_run_context(session_state={})

        # Add to custom list
        with pytest.raises(RetryAgentRun):
            call_tool(add_to_list, context, 'a', list_name='custom')
        with pytest.raises(RetryAgentRun):
            call_tool(add_to_list, context, 'b', list_name='custom')

        result = call_tool(add_to_list, context, 'c', list_name='custom')
        assert '"custom" is complete' in result
        assert 'custom' in context.session_state

    def test_add_to_list_multiple_lists(self):
        """Test add_to_list can manage multiple lists."""
        context = create_run_context(session_state={})

        # Add to default list
        with pytest.raises(RetryAgentRun):
            call_tool(add_to_list, context, 'default1')

        # Add to another list
        with pytest.raises(RetryAgentRun):
            call_tool(add_to_list, context, 'other1', list_name='other')

        # Both lists should exist independently
        assert 'items' in context.session_state
        assert 'other' in context.session_state
        assert context.session_state['items'] == ['default1']
        assert context.session_state['other'] == ['other1']


class TestCheckThresholdTool:
    """Tests for check_threshold tool with StopAgentRun."""

    def test_check_threshold_within_limit(self):
        """Test value within threshold returns success."""
        context = create_run_context(session_state={})

        result = call_tool(check_threshold, context, 50)
        assert 'within the acceptable threshold' in result
        assert '50' in result

    def test_check_threshold_at_limit(self):
        """Test value at threshold is allowed."""
        context = create_run_context(session_state={})

        result = call_tool(check_threshold, context, 100)
        assert 'within the acceptable threshold' in result

    def test_check_threshold_exceeds_limit(self):
        """Test value exceeding threshold raises StopAgentRun."""
        context = create_run_context(session_state={})

        with pytest.raises(StopAgentRun) as exc_info:
            call_tool(check_threshold, context, 101)

        error_msg = str(exc_info.value)
        assert '101' in error_msg
        assert 'exceeds threshold' in error_msg
        assert 'Stopping execution' in error_msg

    def test_check_threshold_custom_threshold(self):
        """Test check_threshold with custom threshold."""
        context = create_run_context(session_state={})

        # Value under custom threshold
        result = call_tool(check_threshold, context, 50, threshold=50)
        assert 'threshold of 50' in result

        # Value over custom threshold
        with pytest.raises(StopAgentRun):
            call_tool(check_threshold, context, 51, threshold=50)

    def test_check_threshold_negative_values(self):
        """Test check_threshold with negative values."""
        context = create_run_context(session_state={})

        # Negative values are always within positive threshold
        result = call_tool(check_threshold, context, -100)
        assert 'within the acceptable threshold' in result

    def test_check_threshold_zero(self):
        """Test check_threshold with zero value."""
        context = create_run_context(session_state={})

        result = call_tool(check_threshold, context, 0)
        assert 'within the acceptable threshold' in result


class TestRunContextIntegration:
    """Integration tests demonstrating RunContext behavior patterns."""

    def test_session_state_persistence_across_calls(self):
        """Test that session state persists across multiple tool calls."""
        context = create_run_context(session_state={})

        # Add items across multiple calls
        for i in range(3):
            try:
                call_tool(add_to_list, context, f'item{i}')
            except RetryAgentRun:
                pass  # Expected for first two items

        # State should accumulate
        assert len(context.session_state['items']) == 3

    def test_multiple_tools_share_context(self):
        """Test that multiple tools can share the same context."""
        context = create_run_context(session_state={'counter': 0})

        # Use check_threshold - it doesn't modify state but shares context
        call_tool(check_threshold, context, 50)

        # Original state should be preserved
        assert context.session_state['counter'] == 0

        # Add items
        with pytest.raises(RetryAgentRun):
            call_tool(add_to_list, context, 'test')

        # Both states coexist
        assert 'counter' in context.session_state
        assert 'items' in context.session_state
