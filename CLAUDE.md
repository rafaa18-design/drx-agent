# Asani AI Agent Template

## Overview

This is an **AI Agent Module Template** that follows the **AgentBench Standard**. It uses the **Agno** framework for agent implementation and **FastAPI** for the API layer.

## Project Structure

```
asani-ai-agent-template/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app with AgentBench endpoints
│   ├── agent.py         # Agno agent configuration
│   ├── models.py        # Pydantic models (AgentBench standard)
│   ├── memory.py        # Conversation memory management
│   ├── config.py        # Application settings
│   └── tools/           # Custom tools
│       └── __init__.py
├── tests/               # Test files
├── pyproject.toml       # uv project configuration
├── .env.example         # Environment variables template
└── CLAUDE.md            # This file
```

## Commands

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload

# Run with Python directly
uv run python -m app.main

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
    { "type": "text", "content": "Hello!" }
  ],
  "conversation_id": "conv_123",
  "model": "claude-sonnet-4-20250514"
}
```

### Response Format (/run)

```json
{
  "conversation_id": "conv_123",
  "final_output": {
    "message": "Hello! How can I help you?",
    "state": {},
    "actions_taken": []
  },
  "metrics": {
    "latency_ms": 320,
    "tokens_used": 57
  }
}
```

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

### Changing the Model

Set the `DEFAULT_MODEL` environment variable or pass `model` in the request.

Supported models:
- Claude: `claude-sonnet-4-20250514`, `claude-3-5-sonnet-20241022`
- OpenAI: `gpt-4o`, `gpt-4-turbo`

### Persistent Memory

For production, replace the in-memory storage in `app/memory.py` with:
- Redis for distributed cache
- PostgreSQL with Agno's `PostgresDb`
- Any other database backend

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MODULE_ID` | Unique module identifier | `asani-agent-template` |
| `MODULE_VERSION` | Semantic version | `1.0.0` |
| `DEFAULT_MODEL` | Default LLM model | `claude-sonnet-4-20250514` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `AGENT_INSTRUCTIONS` | System prompt | `You are a helpful AI assistant.` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
