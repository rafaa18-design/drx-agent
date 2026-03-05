"""Agent utilities and execution loop for litellm-based agent.

This module provides:
- get_litellm_model(): Convert model ID to litellm format string
- get_tools_registry(): Register all tools into a ToolRegistry
- build_system_messages(): Build messages array for litellm
- AgentResponse: Dataclass for agent loop results
- run_agent_loop(): Iterative tool-calling loop with litellm

Optimizations:
- Prompt caching (cache_control on system message + tools) for Anthropic
- Duplicate tool call detection (same tool + same args = cached result)
- Per-tool call limit per turn (prevents infinite loops like listar_servicos x10)
- Parallel tool execution via asyncio.gather when multiple tools in one iteration
"""

import asyncio
import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import litellm

litellm.drop_params = True

from app.config import settings
from app.prompt_manager import get_agent_instructions_sync
from app.runtime import RetryAgentRun, RunContext, StopAgentRun, ToolRegistry
from app.tools import (
    agendar_consulta,
    buscar_paciente,
    calcular_orcamento,
    cancelar_consulta,
    consultar_convenios,
    consultar_historico_paciente,
    listar_servicos,
    obter_data_hora,
    salvar_dados_cliente,
    salvar_preferencias,
    ver_contexto_sessao,
    verificar_cliente,
    verificar_disponibilidade,
)

logger = logging.getLogger(__name__)

# Max times the same tool can be called in a single turn
_MAX_SAME_TOOL_PER_TURN = 3


# ---------------------------------------------------------------------------
# Model & Tools Configuration
# ---------------------------------------------------------------------------


def get_litellm_model(model_id: str | None = None) -> str:
    """Return a litellm model string for the given model ID.

    Supports:
    - Anthropic Claude (anthropic/...)
    - OpenAI GPT (openai/...)
    - Vertex AI Claude (vertex_ai/...)
    """
    model_id = model_id or settings.DEFAULT_MODEL

    # Vertex AI Claude (model IDs contain @ symbol)
    if '@' in model_id or settings.MODEL_PROVIDER == 'vertexai':
        return f'vertex_ai/{model_id}'

    # Anthropic Claude (direct API)
    if 'claude' in model_id.lower():
        return f'anthropic/{model_id}'

    # OpenAI models
    if 'gpt' in model_id.lower() or 'o1' in model_id.lower():
        return f'openai/{model_id}'

    # Default: pass as-is (litellm handles many providers)
    return model_id


def _supports_prompt_caching(model: str) -> bool:
    """Check if the model supports Anthropic-style prompt caching."""
    return 'anthropic/' in model or 'vertex_ai/' in model


def get_agent_instructions() -> str:
    """Get agent instructions synchronously."""
    return get_agent_instructions_sync()


def get_tools_registry() -> ToolRegistry:
    """Register all tools into a ToolRegistry."""
    registry = ToolRegistry()

    all_tools = [
        listar_servicos,
        verificar_disponibilidade,
        agendar_consulta,
        cancelar_consulta,
        buscar_paciente,
        verificar_cliente,
        consultar_historico_paciente,
        consultar_convenios,
        calcular_orcamento,
        salvar_dados_cliente,
        salvar_preferencias,
        ver_contexto_sessao,
        obter_data_hora,
    ]

    for tool_def in all_tools:
        registry.register(tool_def)

    return registry


def build_system_messages(
    instructions: str,
    text_message: str,
    images: list[dict] | None = None,
    history: list[dict] | None = None,
) -> list[dict]:
    """Build messages array for litellm.

    Args:
        instructions: System prompt / agent instructions.
        text_message: User's text message.
        images: Optional list of image content parts (litellm format).
        history: Previous conversation messages (from Redis/memory).

    Returns:
        List of message dicts ready for litellm.acompletion().
    """
    messages = [
        {'role': 'system', 'content': instructions},
    ]

    # Add conversation history for multi-turn context
    if history:
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if content and role in ('user', 'assistant'):
                messages.append({'role': role, 'content': content})

    # Build current user message with optional multimodal content
    if images:
        content_parts = [{'type': 'text', 'text': text_message}]
        content_parts.extend(images)
        messages.append({'role': 'user', 'content': content_parts})
    else:
        messages.append({'role': 'user', 'content': text_message})

    return messages


# ---------------------------------------------------------------------------
# Prompt Caching (Anthropic)
# ---------------------------------------------------------------------------


def _apply_cache_control(
    messages: list[dict],
    tools: list[dict] | None,
) -> tuple[list[dict], list[dict] | None]:
    """Inject cache_control on system message and last tool definition.

    This enables Anthropic's prompt caching, which can reduce input token
    costs by ~90% on subsequent turns (system prompt + tools are stable).
    """
    new_messages = []
    for msg in messages:
        if msg.get('role') == 'system':
            content = msg['content']
            if isinstance(content, str):
                new_content = [{
                    'type': 'text',
                    'text': content,
                    'cache_control': {'type': 'ephemeral'},
                }]
            else:
                # Already a list of content blocks
                new_content = list(content)
                new_content[-1] = {
                    **new_content[-1],
                    'cache_control': {'type': 'ephemeral'},
                }
            new_messages.append({**msg, 'content': new_content})
        else:
            new_messages.append(msg)

    new_tools = tools
    if tools:
        new_tools = list(tools)
        new_tools[-1] = {
            **new_tools[-1],
            'cache_control': {'type': 'ephemeral'},
        }

    return new_messages, new_tools


# ---------------------------------------------------------------------------
# Agent Loop
# ---------------------------------------------------------------------------


@dataclass
class AgentResponse:
    """Result from agent loop execution."""

    content: str
    messages: list[dict[str, Any]]
    input_tokens: int = 0
    output_tokens: int = 0
    tools_used: list[str] = field(default_factory=list)
    session_state: dict[str, Any] = field(default_factory=dict)


def _truncate_tool_output(output: str, max_chars: int | None = None) -> str:
    """Truncate tool output to prevent context bloat."""
    limit = max_chars or settings.TOOL_OUTPUT_MAX_CHARS
    if len(output) <= limit:
        return output
    return output[:limit] + f'\n... [truncated, {len(output)} total chars]'


def _tool_call_key(name: str, args: dict) -> str:
    """Create a hash key for deduplicating identical tool calls."""
    raw = f'{name}:{json.dumps(args, sort_keys=True)}'
    return hashlib.md5(raw.encode()).hexdigest()


async def run_agent_loop(
    messages: list[dict],
    tools: ToolRegistry,
    run_context: RunContext,
    model: str,
    max_iterations: int = 10,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> AgentResponse:
    """Run the agent loop with litellm.

    Optimizations applied:
    - Prompt caching for Anthropic models (system msg + tools cached)
    - Duplicate tool call detection (returns cached result instantly)
    - Per-tool call limit (max 3 calls to same tool per turn)
    - Parallel tool execution (asyncio.gather for independent tools)

    Args:
        messages: Initial messages (system + user).
        tools: ToolRegistry with registered tools.
        run_context: RunContext for tool execution.
        model: litellm model string.
        max_iterations: Maximum tool-calling iterations.
        temperature: LLM temperature.
        max_tokens: Max output tokens per LLM call.

    Returns:
        AgentResponse with the final content and execution metadata.
    """
    total_input_tokens = 0
    total_output_tokens = 0
    tools_used: list[str] = []
    tool_definitions = tools.get_definitions()

    # Prompt caching for Anthropic models
    use_cache = _supports_prompt_caching(model) and settings.CACHE_SYSTEM_PROMPT

    # Per-turn deduplication and frequency tracking
    tool_call_cache: dict[str, str] = {}  # hash → result
    tool_call_counts: Counter = Counter()  # tool_name → count

    for iteration in range(max_iterations):
        # Apply prompt caching if supported
        call_messages = messages
        call_tools = tool_definitions if tool_definitions else None
        if use_cache and call_tools:
            call_messages, call_tools = _apply_cache_control(
                messages, call_tools
            )

        try:
            response = await litellm.acompletion(
                model=model,
                messages=call_messages,
                tools=call_tools,
                tool_choice='auto' if call_tools else None,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            error_str = str(e)
            is_retriable = '503' in error_str or '429' in error_str or 'ServiceUnavailable' in error_str or 'RateLimitError' in error_str
            if not is_retriable:
                logger.error(f'litellm.acompletion failed (iteration {iteration}): {e}')
                raise

            # Retry once on the same model before falling back
            logger.warning(f'Primary model {model} failed ({e}), retrying in 2s...')
            await asyncio.sleep(2)
            try:
                response = await litellm.acompletion(
                    model=model,
                    messages=call_messages,
                    tools=call_tools,
                    tool_choice='auto' if call_tools else None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                logger.info(f'Retry on primary model {model} succeeded')
            except Exception:
                # Try fallback models
                if not settings.FALLBACK_MODELS:
                    logger.error(f'Retry failed and no fallback models configured. Original error: {e}')
                    raise
                response = None
                for fb_model_id in settings.FALLBACK_MODELS:
                    fb_model = get_litellm_model(fb_model_id)
                    logger.warning(f'Primary model retry failed, trying fallback: {fb_model}')
                    try:
                        fb_messages = call_messages
                        fb_tools = call_tools
                        if _supports_prompt_caching(fb_model) and settings.CACHE_SYSTEM_PROMPT and fb_tools:
                            fb_messages, fb_tools = _apply_cache_control(messages, fb_tools)
                        response = await litellm.acompletion(
                            model=fb_model,
                            messages=fb_messages,
                            tools=fb_tools,
                            tool_choice='auto' if fb_tools else None,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                        logger.info(f'Fallback model {fb_model} succeeded')
                        break
                    except Exception as fb_err:
                        logger.warning(f'Fallback model {fb_model} also failed: {fb_err}')
                        continue
                if response is None:
                    logger.error(f'All models (primary + fallbacks) failed. Original error: {e}')
                    raise

        # Track token usage
        usage = getattr(response, 'usage', None)
        if usage:
            total_input_tokens += getattr(usage, 'prompt_tokens', 0) or 0
            total_output_tokens += getattr(usage, 'completion_tokens', 0) or 0
            # Log cache hits for Anthropic
            cache_hits = getattr(usage, 'cache_read_input_tokens', 0)
            if cache_hits:
                logger.debug(
                    f'Prompt cache hit: {cache_hits} tokens saved '
                    f'(iteration {iteration})'
                )

        message = response.choices[0].message

        # If no tool calls, we have the final response
        if not message.tool_calls:
            content = message.content or ''
            return AgentResponse(
                content=content,
                messages=messages,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                tools_used=tools_used,
                session_state=run_context.session_state,
            )

        # Add assistant message with tool calls to conversation
        assistant_msg: dict[str, Any] = {
            'role': 'assistant',
            'content': message.content or '',
            'tool_calls': [
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {
                        'name': tc.function.name,
                        'arguments': tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        }
        messages.append(assistant_msg)

        # Prepare tool executions
        stop_loop = False
        tool_results: list[dict] = []

        # Parse all tool calls first
        parsed_calls: list[tuple[Any, str, dict]] = []
        for tc in message.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                try:
                    from json_repair import repair_json
                    args = json.loads(repair_json(tc.function.arguments))
                except Exception:
                    args = {}
                    logger.warning(
                        f'Failed to parse args for {tool_name}: '
                        f'{tc.function.arguments[:200]}'
                    )
            parsed_calls.append((tc, tool_name, args))

        # Execute tools — with deduplication and frequency limiting
        async def _execute_single_tool(
            tc: Any, tool_name: str, args: dict
        ) -> tuple[str, str, bool]:
            """Execute a single tool, returns (tool_call_id, result, should_stop)."""
            nonlocal tool_call_counts

            tools_used.append(tool_name)
            tool_call_counts[tool_name] += 1

            # Check per-tool frequency limit
            if tool_call_counts[tool_name] > _MAX_SAME_TOOL_PER_TURN:
                logger.warning(
                    f'Tool {tool_name} called {tool_call_counts[tool_name]} '
                    f'times (limit={_MAX_SAME_TOOL_PER_TURN}), returning cached hint'
                )
                return (
                    tc.id,
                    f'Você já chamou {tool_name} {_MAX_SAME_TOOL_PER_TURN} vezes '
                    f'neste turno. Use as informações que já obteve para responder.',
                    False,
                )

            # Check deduplication cache
            cache_key = _tool_call_key(tool_name, args)
            if cache_key in tool_call_cache:
                logger.debug(
                    f'Tool call cache hit: {tool_name}({json.dumps(args)[:80]})'
                )
                return tc.id, tool_call_cache[cache_key], False

            # Execute the tool
            should_stop = False
            try:
                result = await tools.execute(tool_name, args, run_context)
                result = _truncate_tool_output(result)
                # Cache the result for deduplication
                tool_call_cache[cache_key] = result
            except RetryAgentRun as e:
                result = (
                    f'Error: {e.message}'
                    if e.message
                    else 'Error: please retry with corrected parameters.'
                )
            except StopAgentRun as e:
                result = e.message or ''
                should_stop = True

            return tc.id, result, should_stop

        # Execute tools in parallel if multiple, sequentially if single
        if len(parsed_calls) == 1:
            tc, tool_name, args = parsed_calls[0]
            tc_id, result, should_stop = await _execute_single_tool(
                tc, tool_name, args
            )
            messages.append({
                'role': 'tool',
                'tool_call_id': tc_id,
                'content': result,
            })
            if should_stop:
                stop_loop = True
        else:
            # Parallel execution
            tasks = [
                _execute_single_tool(tc, name, args)
                for tc, name, args in parsed_calls
            ]
            results = await asyncio.gather(*tasks)

            for tc_id, result, should_stop in results:
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tc_id,
                    'content': result,
                })
                if should_stop:
                    stop_loop = True

        if stop_loop:
            # Return last available content
            final_content = result if result else (message.content or '')
            return AgentResponse(
                content=final_content,
                messages=messages,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                tools_used=tools_used,
                session_state=run_context.session_state,
            )

    # Max iterations reached
    logger.warning(
        f'Agent loop reached max iterations ({max_iterations})'
    )
    return AgentResponse(
        content=message.content or 'Desculpe, atingi o limite de iterações. Por favor, tente novamente.',
        messages=messages,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        tools_used=tools_used,
        session_state=run_context.session_state,
    )
