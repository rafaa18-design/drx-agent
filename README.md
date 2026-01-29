# Asani AI Agent Template

Template de agente de IA seguindo o padrão **AgentBench** usando o framework **Agno**.

## Features

- **AgentBench Standard**: Endpoints `/metadata`, `/run`, `/run_debug`
- **Multi-Provider**: Anthropic, OpenAI, Google Vertex AI
- **Observabilidade**: Integração com Langfuse
- **Storage**: Redis (cache/sessões) + PostgreSQL (persistência)
- **Autenticação**: JWT com rotas configuráveis

## Quick Start

```bash
# Instalar dependências
uv sync

# Copiar template de ambiente
cp .env.example .env

# Editar .env com suas API keys
# ANTHROPIC_API_KEY=your-key

# Rodar servidor
uv run uvicorn app.main:app --reload
```

## Estrutura

```
app/
├── main.py              # FastAPI + endpoints AgentBench
├── agent.py             # Configuração do agente Agno
├── models.py            # Schemas Pydantic
├── storage.py           # Redis & PostgreSQL
├── config.py            # Settings
├── langfuse_client.py   # Observabilidade
└── tools/               # Ferramentas customizadas
docs/                    # Documentação detalhada (26 arquivos)
```

## Endpoints

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/metadata` | GET | Capacidades do módulo |
| `/run` | POST | Execução em produção |
| `/run_debug` | POST | Debug com trajetória completa |
| `/health` | GET | Health check |

## Exemplo de Request

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"type": "text", "content": "Hello!"}],
    "conversation_id": "test-123"
  }'
```

## Variáveis de Ambiente

| Variável | Descrição |
|----------|-----------|
| `ANTHROPIC_API_KEY` | API key do Anthropic |
| `OPENAI_API_KEY` | API key do OpenAI |
| `DEFAULT_MODEL` | Modelo padrão (default: `claude-sonnet-4-20250514`) |
| `POSTGRES_URL` | URL do PostgreSQL |
| `REDIS_URL` | URL do Redis |
| `LANGFUSE_PUBLIC_KEY` | Chave pública Langfuse |
| `LANGFUSE_SECRET_KEY` | Chave secreta Langfuse |

## Docker

```bash
# Desenvolvimento com Docker Compose
docker-compose up -d

# Ou usando make
make dev
```

## Testes

```bash
uv run pytest
```

## Documentação

Documentação detalhada disponível em:

- **[CLAUDE.md](./CLAUDE.md)** - Índice e guia rápido
- **[docs/](./docs/)** - 26 arquivos de documentação cobrindo:
  - AgentBench, Tools, Agente, Storage
  - State, Memory, Input/Output
  - Knowledge (RAG), Teams, Workflows
  - HITL, RBAC, Observabilidade
  - E mais...
