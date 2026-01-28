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
    AGENT_INSTRUCTIONS: str = 'You are a helpful AI assistant.'
    MAX_TURNS: int = 10

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
