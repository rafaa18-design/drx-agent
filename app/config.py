"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ==========================================================================
    # AgentOS Configuration
    # ==========================================================================
    MODULE_ID: str = 'asani-agent-template'
    MODULE_VERSION: str = '1.0.0'
    MODULE_DESCRIPTION: str = 'Asani AI Agent Template - AgentOS'

    # Agent Identity
    AGENT_NAME: str = 'assistant'
    AGENT_DESCRIPTION: str = (
        'You are a helpful, friendly, and knowledgeable AI assistant. '
        'You remember important details about users and reference them naturally in conversations. '
        'You maintain a warm, professional tone while being precise and helpful. '
        'When appropriate, refer back to previous conversations and what you know about the user.'
    )

    # ==========================================================================
    # Authentication (Agno JWT Middleware)
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

    # ==========================================================================
    # Model Configuration
    # ==========================================================================
    # Model provider: 'anthropic', 'openai', 'vertexai'
    MODEL_PROVIDER: str = 'anthropic'
    DEFAULT_MODEL: str = 'claude-sonnet-4-20250514'

    MODELS_SUPPORTED: list[str] = [
        # Anthropic Direct
        'claude-sonnet-4-20250514',
        'claude-3-5-sonnet-20241022',
        'claude-opus-4-20250514',
        # Vertex AI Claude
        'claude-sonnet-4@20250514',
        'claude-3-5-sonnet-v2@20241022',
        # OpenAI
        'gpt-4o',
        'gpt-4-turbo',
        'gpt-4o-mini',
    ]

    # Anthropic API
    ANTHROPIC_API_KEY: str = ''

    # OpenAI API
    OPENAI_API_KEY: str = ''

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
    AGENT_INSTRUCTIONS_FALLBACK: str = 'You are a helpful AI assistant.'

    MAX_TURNS: int = 10
    NUM_HISTORY_RUNS: int = 3
    COMPRESS_TOOL_RESULTS: bool = True
    TOOL_CALL_LIMIT: int = 5
    MAX_OUTPUT_TOKENS: int = 2048

    # Memory features
    ENABLE_USER_MEMORIES: bool = False
    ENABLE_SESSION_SUMMARIES: bool = False

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
    LANGFUSE_BASE_URL: str = 'https://cloud.langfuse.com'
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
