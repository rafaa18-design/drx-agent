"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ==========================================================================
    # AgentOS Configuration
    # ==========================================================================
    MODULE_ID: str = 'clinica-odontologica'
    MODULE_NAME: str = 'ai-agent'
    MODULE_VERSION: str = '1.0.0'
    MODULE_DESCRIPTION: str = 'Clínica Sorriso - Agente de Atendimento Odontológico'

    # Agent Identity
    AGENT_NAME: str = 'ana-virtual'
    AGENT_DESCRIPTION: str = (
        'Assistente virtual da Clínica Sorriso especializada em atendimento odontológico. '
        'Ajuda pacientes a agendar consultas, consultar serviços, verificar convênios e tirar dúvidas.'
    )

    # ==========================================================================
    # Authentication (JWT)
    # ==========================================================================
    AUTH_ENABLED: bool = True
    JWT_SECRET: str = ''  # Required if AUTH_ENABLED=True
    JWT_ALGORITHM: str = 'HS256'
    JWT_EXPIRATION_HOURS: int = 24

    # User credentials (JSON format: {"username": "password_hash", ...})
    # For development, you can use plain passwords. For production, use bcrypt hashes.
    # Example: AUTH_USERS='{"admin": "$2b$12$...", "user": "$2b$12$..."}'
    AUTH_USERS: str = ''  # Required for /auth/login endpoint

    # Scopes required to create tokens via /auth/token endpoint
    AUTH_ADMIN_SCOPES: list[str] = ['admin', 'tokens:create']

    # Phone allowlist (empty = allow all; set to restrict agent to specific numbers)
    PHONE_ALLOWLIST: list[str] = []

    # ==========================================================================
    # Model Configuration
    # ==========================================================================
    # Model provider: 'anthropic', 'openai', 'vertexai'
    MODEL_PROVIDER: str = 'anthropic'
    DEFAULT_MODEL: str = 'gpt-5-mini'

    MODELS_SUPPORTED: list[str] = [
        # OpenAI
        'gpt-5-mini',
        'gpt-5-nano',
    ]

    # Anthropic API
    ANTHROPIC_API_KEY: str = ''

    # OpenAI API
    OPENAI_API_KEY: str = ''

    # Google Gemini API (used for audio transcription when OpenAI is not available)
    GEMINI_API_KEY: str = ''

    # Vertex AI (Google Cloud)
    GOOGLE_CLOUD_PROJECT: str = ''
    GOOGLE_CLOUD_REGION: str = 'us-east5'
    # GOOGLE_APPLICATION_CREDENTIALS should be set as env var pointing to service account JSON

    # ==========================================================================
    # Agent Behavior
    # ==========================================================================
    AGENT_PROMPT_NAME: str = 'agent-instructions'
    AGENT_PROMPT_VERSION: str | None = None  # None = latest
    AGENT_PROMPT_LABEL: str | None = 'production'
    AGENT_INSTRUCTIONS_FALLBACK: str = (
        'Você é a Ana, assistente virtual da Clínica Sorriso, uma clínica odontológica moderna. '
        'Seu papel é atender pacientes com simpatia e profissionalismo.\n\n'
        'IDIOMA (OBRIGATÓRIO):\n'
        '- SEMPRE responda em português brasileiro. NUNCA use inglês, nem parcialmente.\n'
        '- Toda comunicação deve ser 100% em pt-BR.\n\n'
        'IDENTIDADE:\n'
        '- Sempre se apresente como Ana da Clínica Sorriso na primeira mensagem\n'
        '- Use linguagem acolhedora e profissional\n\n'
        'PRIMEIRA AÇÃO (OBRIGATÓRIO):\n'
        '- Na PRIMEIRA mensagem de cada conversa, SEMPRE chame verificar_cliente antes de responder\n'
        '- Essa tool identifica automaticamente se o canal é de um paciente cadastrado\n'
        '- Se paciente cadastrado: cumprimente pelo nome e use os dados do cadastro\n'
        '- Se paciente novo: trate como primeiro atendimento, informe avaliação gratuita\n'
        '- NUNCA pergunte "você já é paciente?" — a verificação é automática\n\n'
        'REGRAS DE DADOS (CRÍTICO - NÃO VIOLAR):\n'
        '- NUNCA invente, assuma ou deduza dados do paciente\n'
        '- Só mencione dados pessoais se vieram de verificar_cliente ou do CONTEXTO DA SESSÃO\n'
        '- Se não sabe um dado, PERGUNTE ao paciente. Não adivinhe.\n\n'
        'ESTILO DE CONVERSA:\n'
        '- Faça UMA ou no máximo DUAS perguntas por mensagem\n'
        '- Guie a conversa naturalmente, passo a passo\n'
        '- Não despeje listas longas de perguntas de uma vez\n'
        '- Seja breve e direto, sem parágrafos longos\n'
        '- Ordem natural: saudação → entender necessidade → verificar disponibilidade → agendar\n\n'
        'ATENDIMENTO:\n'
        '- Antes de agendar, sempre verifique disponibilidade de horários\n'
        '- Confirme todos os dados com o paciente antes de agendar\n'
        '- Para novos pacientes, informe que a avaliação inicial é gratuita\n'
        '- Se o paciente tiver convênio, mencione a cobertura aplicável\n'
        '- Não forneça diagnósticos ou recomendações médicas\n'
        '- Em caso de emergência, oriente o paciente a ligar: (11) 3000-1234\n\n'
        'LIMITAÇÕES (CRÍTICO - NÃO VIOLAR):\n'
        '- NUNCA prometa ou ofereça funcionalidades que você não possui como ferramenta\n'
        '- Você NÃO pode: enviar SMS, enviar e-mail, enviar WhatsApp, fazer ligações, '
        'enviar notificações, gerar boletos, processar pagamentos\n'
        '- Não pergunte se o paciente quer receber confirmação por SMS/e-mail — você não tem essa capacidade\n'
        '- Após agendar, apenas confirme os dados e encerre. Não sugira envio de lembretes\n'
        '- Só mencione funcionalidades que existem nas suas ferramentas disponíveis\n\n'
        'GESTÃO DE MEMÓRIA:\n'
        '- Use salvar_dados_cliente quando o paciente informar nome, telefone, e-mail, CPF ou convênio\n'
        '- Use salvar_preferencias quando o paciente mencionar horários preferidos, dentista preferido, '
        'alergias, medos ou qualquer observação relevante\n'
        '- Use ver_contexto_sessao se precisar relembrar dados já coletados\n'
        '- Se o CONTEXTO DA SESSÃO estiver presente nas instruções, use esses dados e NÃO pergunte novamente\n'
        '- Ao agendar, use os dados do cliente já salvos no contexto da sessão'
    )

    MAX_TURNS: int = 10
    NUM_HISTORY_RUNS: int = 2
    COMPRESS_TOOL_RESULTS: bool = True
    TOOL_CALL_LIMIT: int = 5
    MAX_OUTPUT_TOKENS: int = 2048

    # Memory features
    ENABLE_USER_MEMORIES: bool = False
    ENABLE_SESSION_SUMMARIES: bool = False

    # Memory Consolidation (LLM-driven)
    MEMORY_CONSOLIDATION_ENABLED: bool = True
    MEMORY_WINDOW: int = 20
    MEMORY_CONSOLIDATION_MODEL: str = ''  # empty = DEFAULT_MODEL
    MEMORY_CONSOLIDATION_MAX_TOKENS: int = 2048
    TOOL_OUTPUT_MAX_CHARS: int = 2000

    # Model optimization
    CACHE_SYSTEM_PROMPT: bool = True
    REASONING_EFFORT: str = 'low'

    # ==========================================================================
    # Storage Configuration
    # ==========================================================================
    # Redis (session state, cache)
    REDIS_URL: str = 'redis://localhost:6379/0'
    REDIS_SESSION_TTL: int = 86400  # 24 hours
    REDIS_CACHE_TTL: int = 3600  # 1 hour
    PROMPT_REDIS_KEY: str = 'agent:prompt:current'
    PROMPT_REDIS_TTL: int = 0  # 0 = no expiry

    # Redis Connection Pool
    REDIS_POOL_MIN_SIZE: int = 5
    REDIS_POOL_MAX_SIZE: int = 20
    REDIS_CONNECT_TIMEOUT: float = 2.0
    REDIS_SOCKET_TIMEOUT: float = 5.0

    # PostgreSQL (persistent storage)
    POSTGRES_URL: str = (
        'postgresql+psycopg://user:password@localhost:5432/agentdb'
    )

    # PostgreSQL Connection Pool
    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_POOL_MAX_OVERFLOW: int = 10
    POSTGRES_POOL_TIMEOUT: float = 30.0
    POSTGRES_POOL_RECYCLE: int = 1800  # 30 minutes

    # ==========================================================================
    # Observability - Langfuse
    # ==========================================================================
    LANGFUSE_PUBLIC_KEY: str = ''
    LANGFUSE_SECRET_KEY: str = ''
    LANGFUSE_BASE_URL: str = 'https://us.cloud.langfuse.com'
    LANGFUSE_ENABLED: bool = True
    LANGFUSE_SIGNATURE_SECRET: str = ''

    # ==========================================================================
    # Observability - OpenTelemetry
    # ==========================================================================
    OTEL_ENABLED: bool = False
    OTEL_ENVIRONMENT: str = 'development'
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ''  # e.g., http://localhost:4317
    OTEL_EXPORTER_OTLP_INSECURE: bool = True

    # ==========================================================================
    # Observability - Prometheus
    # ==========================================================================
    METRICS_ENABLED: bool = True

    # ==========================================================================
    # Server Configuration
    # ==========================================================================
    HOST: str = '0.0.0.0'
    PORT: int = 8000

    # Logging
    LOG_LEVEL: str = 'INFO'
    LOG_FORMAT: str = 'json'  # 'json' for production, 'text' for development

    # CORS - SECURITY: Configure allowed origins for production
    # Default is localhost only. Set CORS_ORIGINS env var for production.
    # Example: CORS_ORIGINS='["https://app.example.com", "https://admin.example.com"]'
    CORS_ORIGINS: list[str] = [
        'http://localhost:3000',
        'http://localhost:8080',
    ]

    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60

    # ==========================================================================
    # Resilience
    # ==========================================================================
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_MIN_WAIT: float = 1.0
    RETRY_MAX_WAIT: float = 10.0

    # Circuit breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: float = 30.0

    # ==========================================================================
    # Graceful Shutdown
    # ==========================================================================
    SHUTDOWN_TIMEOUT: int = 30  # seconds to wait for in-flight requests

    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
        'extra': 'ignore',
    }


settings = Settings()
