# Asani AI Agent Template

## Overview

This is an **AI Agent Module Template** that follows the **AgentBench Standard**. It uses:
- **Agno** framework for agent implementation
- **FastAPI** for the API layer
- **Langfuse** for observability and prompt management
- **Redis** for session state and cache
- **PostgreSQL** for persistent storage

## Project Structure

```
asani-ai-agent-template/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app with AgentBench endpoints
│   ├── agent.py             # Agno agent configuration
│   ├── models.py            # Pydantic models (AgentBench standard)
│   ├── storage.py           # Redis & PostgreSQL backends
│   ├── config.py            # Application settings
│   ├── langfuse_client.py   # Langfuse integration
│   └── tools/               # Custom tools
│       └── __init__.py
├── tests/                   # Test files
├── pyproject.toml           # uv project configuration
├── .env.example             # Environment variables template
└── CLAUDE.md                # This file
```

## Commands

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Linting and formatting
uv run ruff check app/
uv run isort app/
uv run blue app/
```

## AgentBench Standard

This template implements the three required endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/metadata` | GET | Module capabilities and configuration |
| `/run` | POST | Production execution |
| `/run_debug` | POST | Debug execution with full trajectory |

### Request Format

```json
{
  "input": [
    { "type": "text", "content": "Hello!" },
    { "type": "image", "content": "base64...", "mime_type": "image/png" }
  ],
  "conversation_id": "conv_123",
  "model": "claude-sonnet-4-20250514"
}
```

### Supported Input Types

| Type | Formats |
|------|---------|
| text | Plain text |
| image | jpeg, jpg, png, webp |
| audio | mp3, wav, ogg |
| video | mp4, webm |
| document | pdf, txt, md, json, docx, csv |

## Storage Architecture

### Redis (Session & Cache)

Used for fast, ephemeral data:
- **Session state**: Per-conversation state that persists across requests
- **Message history**: Recent messages for context (configurable via `NUM_HISTORY_RUNS`)
- **Cache**: Temporary data with TTL

```python
# Redis keys structure
session:{conversation_id}:state   # Session state JSON
session:{conversation_id}:history # Message list
cache:{key}                       # Cached values
```

### PostgreSQL (Persistent Storage)

Used for durable data via Agno's PostgresDb:
- Agent run history
- Long-term conversation storage
- Audit logs

## Langfuse Integration

### Observability (Tracing)

Every `/run` and `/run_debug` call creates a trace in Langfuse with:
- Session ID (conversation_id)
- Input/output messages
- Latency and token metrics
- Tags for filtering

### Prompt Management

Prompts are fetched from Langfuse by name:
1. Create a prompt in Langfuse UI named `agent-instructions`
2. Add the `production` label to the version you want
3. The agent automatically fetches the latest production prompt

## Customization

### Adding Tools

Edit `app/tools/__init__.py`:

```python
from agno.tools import tool

@tool
def my_custom_tool(param: str) -> str:
    """Tool description for the model."""
    return f"Result: {param}"
```

Then add to the agent in `app/agent.py`:

```python
from app.tools import my_custom_tool

def create_agent(...):
    return Agent(
        ...
        tools=[get_current_time, calculate, my_custom_tool],
    )
```

### Session State

The agent can maintain state across conversation turns:

```python
from agno.run import RunContext

@tool
def add_to_cart(run_context: RunContext, item: str) -> str:
    """Add item to shopping cart."""
    cart = run_context.session_state.get("cart", [])
    cart.append(item)
    run_context.session_state["cart"] = cart
    return f"Added {item} to cart"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MODULE_ID` | Unique module identifier | `asani-agent-template` |
| `MODULE_VERSION` | Semantic version | `1.0.0` |
| `DEFAULT_MODEL` | Default LLM model | `claude-sonnet-4-20250514` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `AGENT_PROMPT_NAME` | Langfuse prompt name | `agent-instructions` |
| `AGENT_INSTRUCTIONS_FALLBACK` | Fallback prompt | `You are a helpful AI assistant.` |
| `NUM_HISTORY_RUNS` | Conversations in context | `10` |
| `COMPRESS_TOOL_RESULTS` | Compress tool outputs | `true` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `REDIS_SESSION_TTL` | Session TTL (seconds) | `86400` |
| `REDIS_CACHE_TTL` | Cache TTL (seconds) | `3600` |
| `POSTGRES_URL` | PostgreSQL connection URL | - |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | - |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | - |
| `LANGFUSE_BASE_URL` | Langfuse API URL | `https://cloud.langfuse.com` |
| `LANGFUSE_ENABLED` | Enable Langfuse | `true` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |

## Docker Compose Example

```yaml
version: '3.8'

services:
  agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - POSTGRES_URL=postgresql+psycopg://agent:secret@postgres:5432/agentdb
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: agentdb
    ports:
      - "5432:5432"
```
