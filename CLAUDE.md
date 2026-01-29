# Asani AI Agent Template

Template de módulo de agente de IA seguindo o padrão **AgentBench** (contrato interno Asani) e usando o framework **Agno**.

## Visão Geral

Este template implementa um módulo de IA compatível com:

- **AgentBench Standard**: Endpoints `/metadata`, `/run`, `/run_debug`
- **Agno Framework**: Framework Python para agentes multi-modais
- **AgentOS**: Runtime de produção do Agno
- **Autenticação JWT**: Middleware com rotas excludas configuráveis
- **Multi-Provider**: Suporte a Anthropic, OpenAI e Vertex AI

### Princípios Chave

| Princípio | Descrição |
|-----------|-----------|
| **Soberania do Módulo** | O módulo é o orquestrador absoluto do seu pipeline interno |
| **Observabilidade** | AgentBench é o observador soberano do comportamento |
| **Estado Gerenciado** | O módulo gerencia seu próprio estado, histórico e contexto |
| **Trajetória Completa** | AgentBench apenas chama endpoints e recebe trajetórias completas |

## Estrutura do Projeto

```
asani-ai-agent-template/
├── app/
│   ├── main.py              # FastAPI + endpoints AgentBench
│   ├── agent.py             # Configuração do agente Agno
│   ├── auth.py              # Autenticação JWT + bcrypt
│   ├── audit.py             # Audit logging para operações sensíveis
│   ├── models.py            # Schemas Pydantic
│   ├── storage.py           # Redis & PostgreSQL (com pooling)
│   ├── config.py            # Settings
│   ├── security.py          # Security headers middleware
│   ├── langfuse_client.py   # Observabilidade Langfuse
│   ├── metrics.py           # Métricas Prometheus
│   ├── tracing.py           # OpenTelemetry tracing
│   ├── profiling.py         # Async profiling utilities
│   ├── rate_limiter.py      # Rate limiting (Redis/in-memory)
│   ├── resilience.py        # Circuit breaker + retry
│   ├── logging_config.py    # Logging estruturado (JSON/text)
│   ├── prompt_manager.py    # Gestão de prompts (Langfuse)
│   └── tools/               # Ferramentas customizadas
│       └── __init__.py
├── scripts/
│   └── hash_password.py     # CLI para gerar hashes bcrypt
├── docs/                    # Documentação detalhada
├── tests/                   # Testes unitários
└── CLAUDE.md                # Este arquivo
```

## Comandos Rápidos

```bash
uv sync                                  # Instalar dependências
uv run uvicorn app.main:app --reload     # Servidor dev
uv run pytest                            # Testes
uv run pytest --cov=app --cov-report=term-missing  # Testes com cobertura
uv run scripts/hash_password.py          # Gerar hash bcrypt
make dev                                 # Docker dev
```

## Documentação

A documentação detalhada está organizada em `docs/`. **Leia o arquivo apropriado para cada contexto:**

### Documentação Principal

| Arquivo | Quando Ler |
|---------|------------|
| [docs/agentbench.md](docs/agentbench.md) | Entender o contrato AgentBench, endpoints `/metadata`, `/run`, `/run_debug` |
| [docs/tools.md](docs/tools.md) | Criar ferramentas, structured output, JSON mode, error handling, hooks em tools |
| [docs/agente.md](docs/agente.md) | Configurar o agente, modelos, providers (Anthropic, OpenAI, Vertex AI), input/output multimodal |
| [docs/storage.md](docs/storage.md) | Session state, memórias, histórico, backends (PostgreSQL, SQLite) |
| [docs/desenvolvimento.md](docs/desenvolvimento.md) | Testes, debugging, Langfuse, troubleshooting, padrões de arquitetura |
| [docs/deploy.md](docs/deploy.md) | Deploy, Docker, segurança, variáveis de ambiente |

### Estado, Dados e Memória

| Arquivo | Quando Ler |
|---------|------------|
| [docs/state.md](docs/state.md) | Session state, gerenciamento de estado entre execuções, múltiplos usuários |
| [docs/memory.md](docs/memory.md) | User memories, agentic memory, session summaries, MemoryTools |
| [docs/input-output.md](docs/input-output.md) | Validação de entrada/saída com Pydantic, structured outputs, JSON mode |

### Recursos Avançados

| Arquivo | Quando Ler |
|---------|------------|
| [docs/knowledge.md](docs/knowledge.md) | RAG, Knowledge Bases, Embedders (OpenAI, Cohere, Google, Ollama), PgVector |
| [docs/teams.md](docs/teams.md) | Multi-Agent Teams (COORDINATE, ROUTE, COLLABORATE) |
| [docs/workflows.md](docs/workflows.md) | Workflows com Steps, Conditions, executores customizados |
| [docs/hooks.md](docs/hooks.md) | Pre/post hooks, tool_hooks, modificação de contexto |
| [docs/reasoning.md](docs/reasoning.md) | Chain-of-thought, ReasoningTools, Extended Thinking (Claude) |
| [docs/guardrails.md](docs/guardrails.md) | Moderação, validação de input/output, guardrails customizados |
| [docs/few-shot.md](docs/few-shot.md) | Few-shot learning com exemplos de conversação |
| [docs/dependencies.md](docs/dependencies.md) | Injeção de dependências via RunContext |

### Multimodal e Streaming

| Arquivo | Quando Ler |
|---------|------------|
| [docs/multimodal.md](docs/multimodal.md) | Imagens, áudio, vídeo - input/output multimodal |
| [docs/streaming.md](docs/streaming.md) | Streaming de respostas, eventos (RunEvent, TeamRunEvent) |
| [docs/async.md](docs/async.md) | Execução assíncrona, FastAPI integration |

### Personalização e Extensões

| Arquivo | Quando Ler |
|---------|------------|
| [docs/culture.md](docs/culture.md) | Personalidade do agente, instructions, estilos de comunicação |
| [docs/skills.md](docs/skills.md) | Skills (SKILL.md, scripts, LocalSkills), skills Anthropic |

### Observabilidade e Integrações

| Arquivo | Quando Ler |
|---------|------------|
| [docs/observability.md](docs/observability.md) | Debug mode, OpenTelemetry, Langfuse, LangSmith, caching |
| [docs/integracao.md](docs/integracao.md) | MCP Tools, Evals, A2A Protocol |
| [docs/agentos.md](docs/agentos.md) | HITL, RBAC, Background Tasks, Remote Execution, MCP Server, Middleware |
| [docs/clients.md](docs/clients.md) | AgentOSClient (REST), A2AClient (protocolo A2A) |

## Guia Rápido por Tarefa

### Criar uma nova ferramenta (tool)

Leia [docs/tools.md](docs/tools.md). Edite `app/tools/__init__.py`:

```python
from agno.tools import tool
from agno.exceptions import RetryAgentRun

@tool
def minha_tool(parametro: str) -> str:
    """Descrição para o LLM."""
    if not valido(parametro):
        raise RetryAgentRun("Feedback para o modelo corrigir")
    return resultado
```

Registre em `app/agent.py` na lista `tools=[]`.

### Modificar configuração do agente

Leia [docs/agente.md](docs/agente.md). Edite `app/agent.py`:

```python
def create_agent(...) -> Agent:
    return Agent(
        model=get_model(model_id),
        tools=[...],
        instructions=instructions,
        # Adicione/modifique configurações aqui
    )
```

### Adicionar novo endpoint

Edite `app/main.py`. Siga o padrão AgentBench documentado em [docs/agentbench.md](docs/agentbench.md).

### Configurar storage/memória

Leia [docs/storage.md](docs/storage.md). Configure em `app/storage.py` e habilite no agente:

```python
agent = Agent(
    db=get_postgres_db(),
    enable_user_memories=True,
    add_history_to_context=True,
)
```

### Implementar RAG/Knowledge

Leia [docs/knowledge.md](docs/knowledge.md) para Knowledge Bases, RAG e Embedders.

### Criar time de agentes

Leia [docs/teams.md](docs/teams.md) para configurar Multi-Agent Teams.

### Human-in-the-Loop (HITL)

Leia [docs/agentos.md](docs/agentos.md) seção "Human-in-the-Loop".

### Configurar RBAC/Autenticação

Leia [docs/agentos.md](docs/agentos.md) seção "RBAC".

### Gerenciar estado entre execuções

Leia [docs/state.md](docs/state.md) para session state e persistência.

### Processar imagens/áudio/vídeo

Leia [docs/multimodal.md](docs/multimodal.md) para input multimodal.

### Validar entrada/saída

Leia [docs/input-output.md](docs/input-output.md) para schemas Pydantic.

### Implementar streaming

Leia [docs/streaming.md](docs/streaming.md) para eventos e streaming.

### Configurar observabilidade

Leia [docs/observability.md](docs/observability.md) para tracing e debug.

### Resolver problemas

Leia [docs/desenvolvimento.md](docs/desenvolvimento.md) seção "Troubleshooting".

### Preparar para produção

Leia [docs/deploy.md](docs/deploy.md).

## Arquivos Importantes

| Arquivo | Propósito |
|---------|-----------|
| `app/main.py` | Endpoints FastAPI, middlewares, lifespan |
| `app/agent.py` | Factory do agente Agno |
| `app/auth.py` | Autenticação JWT com bcrypt |
| `app/tools/__init__.py` | Definição de ferramentas |
| `app/models.py` | Schemas Pydantic para AgentBench |
| `app/config.py` | Configurações (pydantic-settings) |
| `app/metrics.py` | Métricas Prometheus |
| `app/tracing.py` | OpenTelemetry distributed tracing |
| `app/rate_limiter.py` | Rate limiting com Redis |
| `app/resilience.py` | Circuit breaker e retry |
| `scripts/hash_password.py` | CLI para bcrypt |
| `.env` | Variáveis de ambiente locais |
| `PADRAO_AGENT_BENCH.md` | Especificação completa AgentBench |

## Variáveis de Ambiente Essenciais

```bash
# Identidade do módulo
MODULE_ID=meu-agente
MODULE_VERSION=1.0.0

# API Keys (pelo menos uma)
ANTHROPIC_API_KEY=sk-ant-...  # ou OPENAI_API_KEY

# Storage
REDIS_URL=redis://localhost:6379/0
POSTGRES_URL=postgresql+psycopg://user:pass@localhost:5432/agentdb

# Autenticação
AUTH_ENABLED=true
JWT_SECRET=chave-secreta-forte-minimo-32-chars
AUTH_USERS='{"admin": "$2b$12$..."}'  # Use bcrypt! Gerar: uv run scripts/hash_password.py

# CORS - Configure origens específicas para produção
CORS_ORIGINS='["https://app.example.com"]'

# Observabilidade
METRICS_ENABLED=true                    # Prometheus em /metrics
OTEL_ENABLED=false                      # OpenTelemetry tracing
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Resiliência
RETRY_MAX_ATTEMPTS=3
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
SHUTDOWN_TIMEOUT=30
```

## Padrões do Projeto

- **Error Handling**: Use `RetryAgentRun` para feedback ao modelo, `StopAgentRun` para parar execução
- **Tools**: Sempre com docstrings descritivas, validação de inputs
- **Storage**: PostgreSQL em produção, Redis para cache e rate limiting (com connection pooling)
- **Auth**: JWT obrigatório em todos os endpoints exceto `/health`, `/auth/login`, `/metrics`
- **Segurança**: Security headers (HSTS, CSP, X-Frame-Options), bcrypt para senhas, CORS específico
- **Observabilidade**: Métricas Prometheus, tracing OpenTelemetry, logs estruturados, audit logging

## Segurança

### Security Headers

Headers de segurança são adicionados automaticamente a todas as respostas:

- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy` (CSP)
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`

### Audit Logging

Operações sensíveis são registradas automaticamente:

```python
from app.audit import audit_login_success, audit_agent_run_start

# Eventos registrados automaticamente:
# - auth.login.success / auth.login.failure
# - auth.token.created
# - auth.rate_limited
# - agent.run.start / agent.run.success / agent.run.failure
```

## Observabilidade

### Métricas Prometheus (`/metrics`)

```python
# Métricas disponíveis:
# - http_requests_total: Requisições por método/path/status
# - http_request_duration_seconds: Latência das requisições
# - http_requests_in_progress: Requisições em andamento
# - agent_runs_total: Execuções do agente por status
# - agent_run_duration_seconds: Duração das execuções
# - rate_limit_hits_total: Requisições bloqueadas por rate limit
# - circuit_breaker_state: Estado do circuit breaker (0=closed, 1=open, 2=half-open)
```

### OpenTelemetry Tracing

```python
# app/tracing.py
from app.tracing import create_span, get_current_trace_id

async def minha_funcao():
    with create_span('operacao', {'user_id': user_id}) as span:
        result = await processar()
        span.set_attribute('result_size', len(result))
```

### Logging Estruturado

```python
# Formato JSON em produção (LOG_FORMAT=json)
# Formato texto em desenvolvimento (LOG_FORMAT=text)
# Request ID automático em todas as requisições (X-Request-ID)
```

## Resiliência

### Circuit Breaker

```python
from app.resilience import get_circuit_breaker

cb = get_circuit_breaker('external-api')
if cb.can_execute():
    try:
        result = await call_external_api()
        cb.record_success()
    except Exception as e:
        cb.record_failure()
        raise
```

### Retry com Backoff

```python
from app.resilience import retry_with_backoff

result = await retry_with_backoff(
    funcao_que_pode_falhar,
    arg1, arg2,
    max_attempts=3,
    min_wait=1.0,
    max_wait=10.0,
)
```

## Rate Limiting

- Redis-backed com fallback para in-memory
- Sliding window algorithm
- Headers X-RateLimit-* em todas as respostas
- Configurável via `RATE_LIMIT_REQUESTS_PER_MINUTE`

## Graceful Shutdown

- Aguarda requisições em andamento (até SHUTDOWN_TIMEOUT segundos)
- Fecha conexões Redis e PostgreSQL
- Flush de traces e métricas

## Async Profiling

Profile operações async para identificar gargalos:

```python
from app.profiling import profile_async, profile_async_function, get_profiler

# Context manager
async with profile_async('database_query', log_slow_threshold_ms=100):
    result = await db.query(...)

# Decorator
@profile_async_function(log_slow_threshold_ms=200)
async def slow_operation():
    ...

# Ver estatísticas
profiler = get_profiler()
stats = profiler.get_all_stats()  # Ou via GET /profiling
```

## Connection Pooling

Redis e PostgreSQL usam connection pooling configurável:

```bash
# Redis Pool
REDIS_POOL_MIN_SIZE=5
REDIS_POOL_MAX_SIZE=20
REDIS_CONNECT_TIMEOUT=5.0

# PostgreSQL Pool
POSTGRES_POOL_SIZE=5
POSTGRES_POOL_MAX_OVERFLOW=10
POSTGRES_POOL_TIMEOUT=30.0
```

## API Endpoints

### AgentBench (Obrigatórios)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/metadata` | GET | Capacidades do módulo |
| `/run` | POST | Execução em produção |
| `/run_debug` | POST | Execução com trajetória completa |

### Sistema

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/health` | GET | Health check (inclui status Redis/PostgreSQL) |
| `/metrics` | GET | Métricas Prometheus |
| `/profiling` | GET | Estatísticas de profiling async |
| `/` | GET | Informações básicas do módulo |

### Autenticação

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/auth/login` | POST | Obter token JWT (usuário/senha) |
| `/auth/token` | POST | Criar token (requer scope admin) |

### Prompts (Langfuse)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/prompts/webhook` | POST | Webhook para atualização de prompts |
| `/prompts/refresh` | POST | Forçar atualização do prompt |
| `/prompts/current` | GET | Ver prompt atual em cache |

## Autenticação

### Gerar Hash Bcrypt

```bash
# Interativo (com confirmação)
uv run scripts/hash_password.py

# Com senha direta
uv run scripts/hash_password.py --password minha_senha

# Output JSON para .env
uv run scripts/hash_password.py --password minha_senha --json --username admin

# Verificar senha
uv run scripts/hash_password.py --verify '$2b$12$...' --password minha_senha
```

### Configurar Usuários

```bash
# Em .env (use hashes bcrypt em produção!)
AUTH_USERS='{"admin": "$2b$12$xxxxx", "user": "$2b$12$yyyyy"}'
```

### Uso da API

```bash
# Login e obter token
curl -X POST "http://localhost:8000/auth/login?username=admin&password=minha_senha"

# Usar token
curl -H "Authorization: Bearer <token>" http://localhost:8000/metadata

# Criar token para outro usuário (requer scope admin)
curl -H "Authorization: Bearer <admin-token>" \
  -X POST "http://localhost:8000/auth/token?user_id=new_user&scopes=read,write"
```
