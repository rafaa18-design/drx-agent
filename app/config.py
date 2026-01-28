"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Module metadata
    MODULE_ID: str = 'asani-agent-template'
    MODULE_VERSION: str = '1.0.0'
    MODULE_DESCRIPTION: str = 'Asani AI Agent Template - AgentBench Standard'

    # Model configuration
    DEFAULT_MODEL: str = 'claude-sonnet-4-20250514'
    ANTHROPIC_API_KEY: str = ''
    OPENAI_API_KEY: str = ''

    # Agent configuration
    AGENT_PROMPT_NAME: str = 'agent-instructions'
    AGENT_INSTRUCTIONS_FALLBACK: str = 'You are a helpful AI assistant.'
    MAX_TURNS: int = 10
    NUM_HISTORY_RUNS: int = 10
    COMPRESS_TOOL_RESULTS: bool = True

    # Redis configuration (session state, cache)
    REDIS_URL: str = 'redis://localhost:6379/0'
    REDIS_SESSION_TTL: int = 86400  # 24 hours
    REDIS_CACHE_TTL: int = 3600  # 1 hour

    # PostgreSQL configuration (persistent storage)
    POSTGRES_URL: str = (
        'postgresql+psycopg://user:password@localhost:5432/agentdb'
    )

    # Langfuse configuration
    LANGFUSE_PUBLIC_KEY: str = ''
    LANGFUSE_SECRET_KEY: str = ''
    LANGFUSE_BASE_URL: str = 'https://cloud.langfuse.com'
    LANGFUSE_ENABLED: bool = True

    # Server configuration
    HOST: str = '0.0.0.0'
    PORT: int = 8000
    LOG_LEVEL: str = 'INFO'

    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
        'extra': 'ignore',
    }


settings = Settings()
