"""AgentBench Standard routes: /metadata, /run, /run_debug."""

import base64
import tempfile
import time
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter

from app.agent import (
    AgentResponse,
    build_system_messages,
    get_litellm_model,
    get_tools_registry,
    run_agent_loop,
)
from app.config import settings
from app.models import (
    ActionTaken,
    Capabilities,
    DebugMetrics,
    DynamicPromptMapping,
    DynamicPrompts,
    FinalOutput,
    InputItem,
    InputTypes,
    LLMCall,
    MetadataResponse,
    Metrics,
    Pipeline,
    PipelineStage,
    PromptDebug,
    RunDebugResponse,
    RunRequest,
    RunResponse,
    ToolExposed,
    TrajectoryStage,
)
from langfuse import get_client as get_langfuse_client
from langfuse import observe, propagate_attributes

from app.observability import get_logger
from app.prompt_manager import compile_prompt, get_agent_instructions, get_prompt_manager
from app.runtime import RunContext
from app.storage import (
    add_message_to_history,
    get_message_history,
    get_session_state,
    update_session_state,
)
from app.tools import formatar_contexto_completo

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Debug: último input de imagem recebido (para diagnosticar integração WhatsApp)
# ---------------------------------------------------------------------------
_last_image_debug: dict[str, Any] = {}

router_debug = APIRouter(tags=["debug"])

@router_debug.get("/debug/last-image-input")
async def get_last_image_input():
    """Retorna info do último input de imagem recebido (sem os bytes)."""
    return _last_image_debug or {"status": "nenhuma imagem recebida ainda"}


# ---------------------------------------------------------------------------
# Phone Allowlist
# ---------------------------------------------------------------------------

import re


def _normalize_phone(raw: str) -> str:
    """Extract the core phone digits from a conversation_id.

    Handles formats like:
      uazapi-5575998510965, 5575998510965, 75998510965, 998510965
    Returns DDD(2) + number(8) = 10 digits (strips country code and 9th digit).
    """
    digits = re.sub(r'\D', '', raw)
    # Strip country code 55 if present (Brazilian numbers)
    if len(digits) >= 12 and digits.startswith('55'):
        digits = digits[2:]
    # Strip the 9th digit after DDD (mobile numbers: DDD + 9 + 8 digits = 11)
    if len(digits) == 11 and digits[2] == '9':
        digits = digits[:2] + digits[3:]
    return digits


def _is_phone_allowed(conversation_id: str) -> bool:
    """Check if conversation_id matches the phone allowlist.

    Returns True if allowlist is empty (no restriction) or if the
    normalized phone matches any entry in the allowlist.
    """
    if not settings.PHONE_ALLOWLIST:
        return True
    normalized = _normalize_phone(conversation_id)
    for allowed in settings.PHONE_ALLOWLIST:
        if _normalize_phone(allowed) == normalized:
            return True
    return False


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def extract_response_text(response: AgentResponse) -> str:
    """Extract text from AgentResponse."""
    return response.content or ''


def _model_supports_audio(model: str) -> bool:
    """Check if the model natively supports audio input."""
    lower = model.lower()
    # Gemini models support audio natively
    if 'gemini' in lower:
        return True
    return False


def transcribe_audio(audio_bytes: bytes, mime_type: str | None = None) -> str:
    """Transcreve áudio para texto via google.generativeai SDK.

    Usa o mesmo SDK das imagens — compatível com chaves AQ. (Vertex Express)
    e AIza (AI Studio). Fallback para OpenAI Whisper se não tiver chave Gemini.
    """
    # 1. Gemini via google.generativeai SDK
    if settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-2.5-flash')

            audio_part = {
                'mime_type': mime_type or 'audio/mpeg',
                'data': audio_bytes,
            }
            response = model.generate_content([
                'Transcreva este áudio em português. Retorne APENAS o texto transcrito, sem explicações.',
                audio_part,
            ])
            if response.text:
                return response.text.strip()
        except Exception as e:
            logger.error('Gemini transcription error: %s', str(e))

    # 2. Fallback para OpenAI Whisper
    if settings.OPENAI_API_KEY:
        import httpx
        ext = '.mp3'
        if mime_type:
            ext_map = {'audio/ogg': '.ogg', 'audio/mpeg': '.mp3', 'audio/wav': '.wav'}
            ext = ext_map.get(mime_type, '.mp3')

        with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as f:
            f.write(audio_bytes)
            f.flush()
            with open(f.name, 'rb') as audio_file:
                resp = httpx.post(
                    'https://api.openai.com/v1/audio/transcriptions',
                    headers={'Authorization': f'Bearer {settings.OPENAI_API_KEY}'},
                    files={'file': (f'audio{ext}', audio_file)},
                    data={'model': 'gpt-4o-mini-transcribe', 'language': 'pt'},
                    timeout=30.0,
                )
                if resp.status_code == 200:
                    return resp.json().get('text', '')
                logger.error('Whisper transcription failed: status=%s body=%s', resp.status_code, resp.text[:300])

    return '[audio não transcrito]'


def analyze_image_direct(image_bytes: bytes, mime_type: str | None = None) -> str | None:
    """Analisa imagem com Gemini Flash e retorna descrição estruturada para o agente.

    Retorna None em caso de falha — caller decide o fallback.
    """
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        mime = mime_type or 'image/jpeg'
        image_part = {'mime_type': mime, 'data': image_bytes}

        prompt = (
            'Analise esta imagem e classifique-a em uma das categorias abaixo.\n\n'
            'CATEGORIA A — Print de PROBLEMA em rede social:\n'
            'Exemplos: tela de banimento, restrição, conta desativada, aviso, suspensão, bloqueio de funcionalidades.\n'
            'Se for categoria A, retorne:\n'
            '- Plataforma afetada (Instagram, TikTok, YouTube, etc.)\n'
            '- Tipo do problema (banimento permanente, restrição temporária, aviso, etc.)\n'
            '- Gravidade (permanente, temporário, apenas aviso)\n'
            '- Texto principal visível na tela\n\n'
            'CATEGORIA B — Print de PERFIL de rede social:\n'
            'Exemplos: página de perfil com seguidores, bio, foto de capa.\n'
            'Se for categoria B, retorne:\n'
            '- Plataforma\n'
            '- Nome/usuário\n'
            '- Número de seguidores\n'
            '- Sinais de monetização ou uso profissional\n\n'
            'CATEGORIA C — Imagem NÃO relacionada (foto de pessoas, paisagens, documentos, etc.):\n'
            'Retorne exatamente: [IMAGEM_INVALIDA]\n\n'
            'Seja direto. Máximo 5 linhas para A e B. Apenas [IMAGEM_INVALIDA] para C.'
        )

        response = model.generate_content([prompt, image_part])
        if response.text and response.text.strip():
            logger.info('analyze_image_direct: ok (%d chars) → %s', len(response.text), response.text[:120])
            return response.text.strip()
        logger.warning('analyze_image_direct: resposta vazia (blocked? candidates=%s)', getattr(response, 'candidates', 'N/A'))

    except Exception as e:
        logger.error('analyze_image_direct falhou: %s (type=%s, bytes=%d, mime=%s)', str(e), type(e).__name__, len(image_bytes), mime_type)

    return None


def parse_multimodal_input(
    items: list[InputItem],
    model: str = '',
    conversation_id: str = '',
) -> tuple[str, list[dict]]:
    """Parse multimodal input items into litellm content parts.

    Imagens são analisadas via Gemini Flash direto e armazenadas no image_store
    para uso pelas vision tools sem necessidade de repassar base64.

    Args:
        items: Input items from the request.
        model: The litellm model string (usado para verificar suporte a áudio nativo).
        conversation_id: ID da conversa para indexar as imagens no cache.

    Returns:
        Tuple of (text_message, media_content_parts).
    """
    from app.tools.drx.image_store import store_image

    text_parts: list[str] = []
    media: list[dict] = []

    for item in items:
        if item.type == 'text':
            text_parts.append(item.content)
        elif item.type == 'image':
            mime = item.mime_type or 'image/jpeg'
            filename = item.filename or 'imagem'
            raw = (item.content or '').strip()

            # Log + captura para debug — mostra o formato recebido
            logger.info(
                'IMAGE INPUT: len=%d, starts=%r, mime=%s, filename=%s',
                len(raw), raw[:120], mime, filename,
            )
            _last_image_debug.update({
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'content_length': len(raw),
                'content_preview': raw[:200],
                'mime_type': mime,
                'filename': filename,
                'conversation_id': conversation_id,
            })

            content_bytes: bytes | None = None

            # 1) URL de mídia (WhatsApp / Evolution API)
            if raw.startswith('http://') or raw.startswith('https://'):
                try:
                    import httpx as _hx
                    r = _hx.get(raw, timeout=30, follow_redirects=True)
                    r.raise_for_status()
                    content_bytes = r.content
                    if r.headers.get('content-type', '').startswith('image/'):
                        mime = r.headers['content-type'].split(';')[0]
                    logger.info('Imagem baixada de URL: %d bytes, mime=%s', len(content_bytes), mime)
                except Exception as e:
                    logger.error('Falha ao baixar imagem de URL %s: %s', raw[:100], e)

            # 2) Data URI (data:image/png;base64,iVBOR...)
            elif raw.startswith('data:'):
                try:
                    header, b64data = raw.split(',', 1)
                    if 'image/' in header:
                        mime = header.split(':')[1].split(';')[0]
                    content_bytes = base64.b64decode(b64data)
                    logger.info('Imagem decodificada de data URI: %d bytes', len(content_bytes))
                except Exception as e:
                    logger.error('Falha ao decodificar data URI: %s', e)

            # 3) Base64 puro (chat web)
            elif raw:
                try:
                    content_bytes = base64.b64decode(raw)
                    logger.info('Imagem decodificada de base64: %d bytes', len(content_bytes))
                except Exception as e:
                    logger.error('Falha ao decodificar base64: %s (primeiros 80 chars: %r)', e, raw[:80])

            if not content_bytes or len(content_bytes) < 100:
                logger.warning('IMAGE: bytes vazios ou muito pequenos (%d), raw[:80]=%r', len(content_bytes or b''), raw[:80])
                text_parts.append(
                    f'[Print recebido: {filename}] '
                    f'Não consegui processar a imagem. '
                    f'Informe o lead que recebeu e pergunte o que está escrito na tela.'
                )
                continue

            # Guarda no cache para as vision tools atualizarem o CRM
            if conversation_id:
                store_image(conversation_id, content_bytes, mime, filename)

            # Analisa server-side — o agente recebe o resultado pronto
            analysis = analyze_image_direct(content_bytes, mime)

            if analysis == '[IMAGEM_INVALIDA]':
                text_parts.append(
                    f'[Imagem recebida: {filename}] '
                    f'IMAGEM NÃO RELACIONADA AO CASO — não é print de problema nem perfil de rede social. '
                    f'Peça educadamente que o lead envie o print correto do problema ou do perfil.'
                )
            elif analysis:
                text_parts.append(
                    f'[Print recebido do lead — {filename}]\n'
                    f'{analysis}\n'
                    f'[Use analyze_problem_print ou analyze_profile_print para salvar no CRM]'
                )
            else:
                text_parts.append(
                    f'[Print recebido: {filename}] '
                    f'Não consegui ler a imagem. '
                    f'Informe o lead que recebeu e pergunte o que está escrito na tela.'
                )
        elif item.type == 'audio':
            content_bytes = base64.b64decode(item.content)
            if _model_supports_audio(model):
                # Pass audio natively to the model
                b64_str = base64.b64encode(content_bytes).decode('utf-8')
                mime = item.mime_type or 'audio/mpeg'
                media.append({
                    'type': 'input_audio',
                    'input_audio': {'data': b64_str, 'format': mime},
                })
            else:
                # Transcribe audio to text
                transcription = transcribe_audio(content_bytes, item.mime_type)
                if transcription:
                    text_parts.append(f'[Audio do usuário]: {transcription}')
        elif item.type == 'video':
            text_parts.append('[Vídeo enviado pelo usuário - não suportado para análise direta]')
        elif item.type == 'document':
            text_parts.append(
                f'[Documento enviado: {item.filename or "documento"}]'
            )

    text_message = '\n'.join(text_parts) if text_parts else ''
    return text_message, media


def extract_actions_from_response(response: AgentResponse) -> list[ActionTaken]:
    """Extract tool calls from the AgentResponse."""
    actions = []
    for tool_name in response.tools_used:
        actions.append(
            ActionTaken(
                tool=tool_name,
                success=True,
                error=None,
            )
        )
    return actions


@dataclass
class AgentRunResult:
    """Result from agent execution."""

    response: AgentResponse | None
    instructions: str
    session_state: dict[str, Any]
    latency_ms: float
    input_tokens: int
    output_tokens: int
    text_message: str
    actions: list[ActionTaken]
    error: Exception | None = None


@observe(name="agent-run")
async def execute_agent(
    request: RunRequest,
    debug: bool = False,
) -> AgentRunResult:
    """Execute agent and return unified result."""
    from app.audit import (
        audit_agent_run_failure,
        audit_agent_run_start,
        audit_agent_run_success,
    )
    from app.memory import (
        get_memory_context,
        increment_unconsolidated,
        schedule_consolidation,
        should_consolidate,
    )

    start_time = time.perf_counter()
    conversation_id = request.conversation_id

    # Phone allowlist check (early return — no LLM cost)
    if not _is_phone_allowed(conversation_id):
        logger.info(f'Phone {conversation_id} not in allowlist, skipping')
        return AgentRunResult(
            response=None,
            instructions='',
            session_state={},
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            text_message='',
            actions=[],
            error=None,
        )

    model_id = request.model or settings.DEFAULT_MODEL
    error: Exception | None = None
    response: AgentResponse | None = None
    instructions = ''
    session_state: dict[str, Any] = {}
    text_message = ''
    input_tokens = 0
    output_tokens = 0
    actions: list[ActionTaken] = []

    try:
        # Parse multimodal input (passa conversation_id para indexar imagens no cache)
        model = get_litellm_model(model_id)
        text_message, images = parse_multimodal_input(
            request.input, model=model, conversation_id=conversation_id
        )

        # Audit log run start
        audit_agent_run_start(
            user_id=conversation_id,
            session_id=conversation_id,
            model=model_id,
            input_length=len(text_message),
        )

        # Get session state from Redis
        session_state = await get_session_state(conversation_id)

        t0 = time.perf_counter()
        template = await get_agent_instructions()
        t1 = time.perf_counter()
        logger.info(
            f'[PERF] get_instructions: {(t1-t0)*1000:.0f}ms',
            extra={'request_id': ''},
        )

        # Get memory context (consolidated facts)
        memory_context = ''
        if settings.MEMORY_CONSOLIDATION_ENABLED:
            memory_context = await get_memory_context(conversation_id)

        # Format full context (memory + session state)
        full_context = formatar_contexto_completo(session_state, memory_context)

        instructions = compile_prompt(
            template,
            session_context=full_context,
        )

        # Build litellm model string
        model = get_litellm_model(model_id)

        # Fetch conversation history for multi-turn context
        history = await get_message_history(conversation_id)

        # Build messages
        messages = build_system_messages(
            instructions, text_message, images or None, history=history
        )

        # Create RunContext and tools registry
        run_context = RunContext(
            session_state=session_state,
            session_id=conversation_id,
            user_id=conversation_id,
        )
        registry = get_tools_registry()

        # Execute agent loop (Langfuse context propagated from run())
        response = await run_agent_loop(
            messages=messages,
            tools=registry,
            run_context=run_context,
            model=model,
            max_iterations=settings.MAX_TURNS,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
        )

        # Store messages in Redis
        response_text = extract_response_text(response)
        await add_message_to_history(conversation_id, 'user', text_message)
        await add_message_to_history(
            conversation_id, 'assistant', response_text
        )

        # Sincroniza com o CRM (lead + conversa + mensagens) — garante que
        # toda conversa apareça no dashboard, mesmo sem chamadas de tool.
        from app.services.crm_sync import sync_conversation_turn
        await sync_conversation_turn(
            conversation_id,
            text_message,
            response_text,
            response.session_state or {},
        )

        # Update session state from RunContext (tools may have modified it)
        if response.session_state:
            await update_session_state(
                conversation_id, response.session_state
            )
            session_state = response.session_state

        # Token info
        input_tokens = response.input_tokens
        output_tokens = response.output_tokens

        actions = extract_actions_from_response(response)

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Memory consolidation (increment twice: 1 for user msg, 1 for assistant msg)
        if settings.MEMORY_CONSOLIDATION_ENABLED:
            await increment_unconsolidated(conversation_id)
            await increment_unconsolidated(conversation_id)
            if await should_consolidate(conversation_id):
                schedule_consolidation(conversation_id)

        # Audit log success
        audit_agent_run_success(
            user_id=conversation_id,
            session_id=conversation_id,
            model=model_id,
            duration_ms=latency_ms,
            tokens_used=input_tokens + output_tokens,
            tool_calls=len(actions),
        )

    except Exception as e:
        error = e
        logger.error(f'Agent run failed for {conversation_id}: {e}')
        latency_ms = (time.perf_counter() - start_time) * 1000
        audit_agent_run_failure(
            user_id=conversation_id,
            session_id=conversation_id,
            model=model_id,
            error=str(e),
            duration_ms=latency_ms,
        )

    latency_ms = (time.perf_counter() - start_time) * 1000

    # Set trace I/O for Langfuse visibility
    try:
        lf = get_langfuse_client()
        lf.set_current_trace_io(
            input={'message': text_message, 'conversation_id': conversation_id},
            output={'response': extract_response_text(response) if response else '', 'tools_used': actions},
        )
        lf.flush()
    except Exception:
        pass

    return AgentRunResult(
        response=response,
        instructions=instructions,
        session_state=session_state,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        text_message=text_message,
        actions=actions,
        error=error,
    )


# ---------------------------------------------------------------------------
# Tools metadata cache
# ---------------------------------------------------------------------------

_cached_tools_metadata: list[ToolExposed] | None = None


def _get_tools_metadata() -> list[ToolExposed]:
    """Return cached tool metadata for the /metadata endpoint."""
    global _cached_tools_metadata
    if _cached_tools_metadata is not None:
        return _cached_tools_metadata

    registry = get_tools_registry()
    tools = []
    for tool_def in registry._tools.values():
        params = tool_def.parameters.get('properties', {})
        parameters_schema = None
        if params:
            parameters_schema = {
                k: v.get('type', 'any') for k, v in params.items()
            }
        tools.append(
            ToolExposed(
                name=tool_def.name,
                description=tool_def.description,
                parameters_schema=parameters_schema,
            )
        )

    _cached_tools_metadata = tools
    return tools


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

agentbench_router = APIRouter(tags=['AgentBench'])


@agentbench_router.get('/metadata', response_model=MetadataResponse)
async def get_metadata() -> MetadataResponse:
    """Return module metadata following AgentBench standard."""
    pipeline = Pipeline(
        is_monolithic=True,
        stages=[
            PipelineStage(
                id='main', type='agent', model_configurable=True
            )
        ],
    )
    dynamic_prompts = DynamicPrompts(
        state_key='mode',
        mapping=[
            DynamicPromptMapping(
                state_value='default',
                base_system_prompt=settings.AGENT_INSTRUCTIONS_FALLBACK,
                expected_context_keys=['user_profile'],
            ),
        ],
    )

    return MetadataResponse(
        module_id=settings.MODULE_ID,
        version=settings.MODULE_VERSION,
        description=settings.MODULE_DESCRIPTION,
        capabilities=Capabilities(
            supports_multi_stage=False,
            supports_dynamic_system_prompt=True,
            supports_cross_model=True,
            supports_jailbreak_tests=True,
        ),
        pipeline=pipeline,
        dynamic_prompts=dynamic_prompts,
        tools_exposed=_get_tools_metadata(),
        input_types=InputTypes(
            supported_types=['text', 'image', 'audio'],
            allowed_formats={
                'image': ['jpeg', 'jpg', 'png', 'webp'],
                'audio': ['mp3', 'wav', 'ogg'],
            },
        ),
        models_supported=settings.MODELS_SUPPORTED,
    )


@agentbench_router.post('/run', response_model=RunResponse)
async def run(request: RunRequest) -> RunResponse:
    """Execute the agent in production mode (AgentBench standard)."""
    logger.info(f'Running agent for conversation: {request.conversation_id}')

    # Handle /reset command — clear session without calling LLM
    if settings.RESET_COMMAND_ENABLED:
        raw_text = ' '.join(
            item.content for item in request.input if item.type == 'text'
        ).strip()
        if raw_text.lower() == '/reset':
            from app.memory import clear_memory
            from app.storage import clear_message_history, delete_session_state

            cid = request.conversation_id
            await delete_session_state(cid)
            await clear_message_history(cid)
            await clear_memory(cid)
            logger.info(f'Session reset via /reset command: {cid}')

            return RunResponse(
                conversation_id=cid,
                final_output=FinalOutput(
                    message='Sessão reiniciada! Como posso ajudá-lo(a)?',
                    state=None,
                    actions_taken=None,
                ),
                metrics=Metrics(latency_ms=0, tokens_used=None, cost_estimate=None),
            )

    # Propagate Langfuse attributes BEFORE calling execute_agent
    # so @observe trace inherits session_id, user_id, tags
    with propagate_attributes(
        user_id=request.conversation_id,
        session_id=request.conversation_id,
        tags=[settings.AGENT_NAME],
    ):
        result = await execute_agent(request, debug=False)

    if result.error:
        return RunResponse(
            conversation_id=request.conversation_id,
            final_output=FinalOutput(
                message='An error occurred while processing your request.',
                state=None,
                actions_taken=None,
            ),
            metrics=Metrics(
                latency_ms=result.latency_ms,
                tokens_used=None,
                cost_estimate=None,
            ),
        )

    tokens_used = (
        result.input_tokens + result.output_tokens
        if result.input_tokens or result.output_tokens
        else None
    )

    message = extract_response_text(result.response) if result.response else ''

    if not message:
        logger.warning(
            'Agent response empty for %s',
            request.conversation_id,
        )

    logger.info(
        f'Agent run completed for {request.conversation_id} '
        f'in {result.latency_ms:.2f}ms'
    )

    return RunResponse(
        conversation_id=request.conversation_id,
        final_output=FinalOutput(
            message=message,
            state=result.session_state if result.session_state else None,
            actions_taken=result.actions if result.actions else None,
        ),
        metrics=Metrics(
            latency_ms=result.latency_ms,
            tokens_used=tokens_used,
            cost_estimate=None,
        ),
    )


@agentbench_router.post('/run_debug', response_model=RunDebugResponse)
async def run_debug(request: RunRequest) -> RunDebugResponse:
    """Execute the agent in debug mode (AgentBench standard)."""
    logger.info(
        f'Running agent (debug) for conversation: {request.conversation_id}'
    )

    result = await execute_agent(request, debug=True)

    if result.error:
        return RunDebugResponse(
            conversation_id=request.conversation_id,
            final_output=FinalOutput(
                message=f'An error occurred: {str(result.error)}',
                state=None,
                actions_taken=None,
            ),
            trajectory=[
                TrajectoryStage(
                    stage_id='error',
                    type='agent',
                    sequence=1,
                    prompt_debug=PromptDebug(
                        final_system_prompt_used='Error occurred',
                    ),
                    llm_calls=[],
                    latency_ms=result.latency_ms,
                    errors=[str(result.error)],
                )
            ],
            metrics=DebugMetrics(
                total_latency_ms=result.latency_ms,
                total_tokens={'input': 0, 'output': 0},
                llm_calls=0,
            ),
        )

    message = extract_response_text(result.response) if result.response else ''

    # Build trajectory
    trajectory = [
        TrajectoryStage(
            stage_id='main',
            type='agent',
            sequence=1,
            prompt_debug=PromptDebug(
                final_system_prompt_used=result.instructions,
            ),
            llm_calls=[
                LLMCall(
                    model=request.model or settings.DEFAULT_MODEL,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
            ],
            latency_ms=result.latency_ms,
        )
    ]
    llm_calls_count = 1

    logger.info(
        f'Agent debug run completed for {request.conversation_id} '
        f'in {result.latency_ms:.2f}ms'
    )

    return RunDebugResponse(
        conversation_id=request.conversation_id,
        final_output=FinalOutput(
            message=message,
            state=result.session_state if result.session_state else None,
            actions_taken=result.actions if result.actions else None,
        ),
        trajectory=trajectory,
        metrics=DebugMetrics(
            total_latency_ms=result.latency_ms,
            total_tokens={
                'input': result.input_tokens,
                'output': result.output_tokens,
            },
            llm_calls=llm_calls_count,
        ),
    )
