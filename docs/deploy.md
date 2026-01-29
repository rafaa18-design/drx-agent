# Deploy e Produção

Este documento cobre deploy, configuração de ambiente e segurança.

---

## Variáveis de Ambiente

### Produção Mínima

```bash
# Identificação
MODULE_ID=meu-agente
MODULE_VERSION=1.0.0

# LLM (pelo menos um)
ANTHROPIC_API_KEY=sk-ant-...
# ou
OPENAI_API_KEY=sk-...

# Autenticação
AUTH_ENABLED=true
JWT_SECRET=chave-secreta-longa-e-segura-minimo-32-chars

# Storage
POSTGRES_URL=postgresql+psycopg://user:pass@host:5432/db
```

### Opcional: Observabilidade

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_ENABLED=true
```

### Todas as Variáveis

| Variável | Descrição | Default |
|----------|-----------|---------|
| `MODULE_ID` | ID único do módulo | `asani-agent-template` |
| `MODULE_VERSION` | Versão semântica | `1.0.0` |
| `DEFAULT_MODEL` | Modelo padrão | `claude-sonnet-4-20250514` |
| `AUTH_ENABLED` | Habilitar autenticação | `true` |
| `JWT_SECRET` | Chave para tokens JWT | - |
| `POSTGRES_URL` | URL do PostgreSQL | - |
| `NUM_HISTORY_RUNS` | Mensagens no contexto | `10` |
| `CACHE_SYSTEM_PROMPT` | Cache de prompt | `true` |

---

## Docker Compose

### Produção

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  agent:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - MODULE_ID=${MODULE_ID}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - POSTGRES_URL=postgresql+psycopg://agent:${DB_PASSWORD}@postgres:5432/agentdb
      - AUTH_ENABLED=true
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: agentdb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent -d agentdb"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copiar arquivos de dependências
COPY pyproject.toml uv.lock ./

# Instalar dependências
RUN uv sync --frozen --no-dev

# Copiar código
COPY app/ app/

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Executar
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Segurança

### Boas Práticas

| Aspecto | Recomendação |
|---------|--------------|
| JWT_SECRET | Mínimo 32 caracteres, único por ambiente |
| API Keys | Nunca commitar, usar secrets manager |
| POSTGRES_URL | Senha forte, SSL em produção |
| Endpoints | Sempre autenticar exceto health/login |
| Tools | Validar inputs, não executar código arbitrário |
| Logs | Não logar dados sensíveis |

### Validação em Tools

```python
from agno.exceptions import RetryAgentRun, StopAgentRun
import re


def processar_email(run_context: RunContext, email: str) -> str:
    """Tool com validação de input."""
    # Validar formato
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        raise RetryAgentRun(
            "Email inválido. Use formato: usuario@dominio.com"
        )

    # Validar domínio
    blocked_domains = ['spam.com', 'fake.com']
    domain = email.split('@')[1]
    if domain in blocked_domains:
        raise StopAgentRun("Domínio bloqueado.")

    return f"Email {email} processado"
```

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/run")
@limiter.limit("10/minute")
async def run(request: RunRequest):
    ...
```

---

## Checklist de Deploy

### Pré-Deploy

- [ ] Todas as variáveis de ambiente configuradas
- [ ] JWT_SECRET é único e seguro
- [ ] API keys configuradas
- [ ] PostgreSQL acessível
- [ ] Testes passando

### Deploy

- [ ] Docker build sem erros
- [ ] Healthcheck funcionando
- [ ] Logs sem erros críticos
- [ ] Métricas sendo coletadas

### Pós-Deploy

- [ ] Endpoint `/health` retorna 200
- [ ] Endpoint `/metadata` retorna dados corretos
- [ ] Autenticação funcionando
- [ ] `/run` processa requisições
- [ ] Observabilidade configurada (Langfuse)

---

## Monitoramento

### Endpoints de Health

```bash
# Health básico
curl http://localhost:8000/health

# Metadata
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/metadata
```

### Logs Estruturados

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "request_processed",
    conversation_id=conversation_id,
    latency_ms=latency_ms,
    tokens_used=tokens_used,
)
```

---

## Comandos de Deploy

```bash
# Build e deploy com Docker Compose
docker-compose -f docker-compose.prod.yml up -d --build

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f agent

# Restart
docker-compose -f docker-compose.prod.yml restart agent

# Scale (se usando swarm/k8s)
docker service scale agent=3
```

---

## Migrações em Produção

```bash
# Rodar migrações Alembic antes do deploy
make migrate

# Migrações do Agno (sessions, memories)
make agno-migrate

# Ou manualmente
uv run python -c "
from agno.db.postgres import PostgresDb
db = PostgresDb(db_url='postgresql+psycopg://...')
db.create_tables()
"
```

---

## Referências

- [Docker Documentation](https://docs.docker.com)
- [Uvicorn Deployment](https://www.uvicorn.org/deployment/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
