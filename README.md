# Asani AI Agent Template

AI Agent Module Template following the **AgentBench Standard** using the **Agno** framework.

## Quick Start

```bash
# Install dependencies
uv sync

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
# ANTHROPIC_API_KEY=your-key

# Run the server
uv run uvicorn app.main:app --reload
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/metadata` | GET | Module capabilities |
| `/run` | POST | Production execution |
| `/run_debug` | POST | Debug with trajectory |
| `/health` | GET | Health check |

## Example Request

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"type": "text", "content": "Hello!"}],
    "conversation_id": "test-123"
  }'
```

## Documentation

See [CLAUDE.md](./CLAUDE.md) for detailed documentation.
