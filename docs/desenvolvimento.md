# Desenvolvimento e Testes

Este documento cobre testes, debugging, troubleshooting e boas práticas de desenvolvimento.

---

## Estrutura de Testes

```
tests/
├── __init__.py
├── conftest.py        # Fixtures compartilhadas
├── test_api.py        # Testes de endpoints
├── test_tools.py      # Testes de tools
└── test_agent.py      # Testes do agente
```

---

## Fixtures Úteis

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Cliente de teste sem autenticação."""
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """Cliente de teste com JWT válido."""
    response = client.post(
        '/auth/login',
        params={'username': 'test', 'password': 'password'},
    )
    if response.status_code == 200:
        token = response.json().get('access_token')
        client.headers['Authorization'] = f'Bearer {token}'
    return client
```

---

## Testando Tools

```python
# tests/test_tools.py
import pytest
from agno.exceptions import RetryAgentRun, StopAgentRun
from app.tools import calculate, format_date


def call_tool(tool_func, *args, **kwargs):
    """Helper para chamar tools do Agno."""
    if hasattr(tool_func, 'func'):
        return tool_func.func(*args, **kwargs)
    elif hasattr(tool_func, 'entrypoint'):
        return tool_func.entrypoint(*args, **kwargs)
    return tool_func(*args, **kwargs)


class TestCalculateTool:
    def test_simple_addition(self):
        assert call_tool(calculate, '2 + 2') == '4'

    def test_division_by_zero_raises_retry(self):
        with pytest.raises(RetryAgentRun) as exc:
            call_tool(calculate, '10 / 0')
        assert 'Division by zero' in str(exc.value)


class TestFormatDateTool:
    def test_iso_format(self):
        result = call_tool(format_date, '2024-01-15')
        assert result == '2024-01-15'

    def test_invalid_date_raises_retry(self):
        with pytest.raises(RetryAgentRun):
            call_tool(format_date, 'invalid')
```

---

## Testando Endpoints AgentBench

```python
# tests/test_api.py
class TestAgentBenchEndpoints:
    def test_metadata(self, auth_client):
        response = auth_client.get('/metadata')
        assert response.status_code == 200
        data = response.json()
        assert 'module_id' in data
        assert 'capabilities' in data

    def test_run_validation(self, auth_client):
        response = auth_client.post('/run', json={})
        assert response.status_code == 422

    def test_run_with_valid_input(self, auth_client):
        response = auth_client.post('/run', json={
            'input': [{'type': 'text', 'content': 'Olá'}],
            'conversation_id': 'test_001',
        })
        assert response.status_code == 200
        data = response.json()
        assert 'final_output' in data
        assert 'metrics' in data
```

---

## Rodando Testes

```bash
# Todos os testes
make test

# Com coverage
uv run pytest --cov=app --cov-report=html

# Testes específicos
uv run pytest tests/test_tools.py -v

# Testes com keyword
uv run pytest -k "calculate" -v
```

---

## Troubleshooting

### Problemas Comuns

| Problema | Causa | Solução |
|----------|-------|---------|
| API Key não encontrada | pydantic-settings não exporta | Passar `api_key=` explicitamente |
| 401 em endpoints | JWT incorreto | Verificar `excluded_route_paths` |
| Tool não chamada | Docstring inadequada | Melhorar descrição |
| Memória não persiste | DB não configurado | Adicionar `db=` ao agente |
| Rate limit | Muitas requisições | Habilitar `exponential_backoff=True` |
| Histórico não funciona | session_id não definido | Passar `session_id=` |
| Tool retorna erro | Exceção não tratada | Usar `RetryAgentRun` |

### Debug de Tools

```python
from agno.utils.log import logger

def minha_tool(run_context: RunContext, param: str) -> str:
    """Tool com logging para debug."""
    logger.info(f"Tool chamada com: {param}")
    logger.debug(f"Session state: {run_context.session_state}")

    try:
        resultado = processar(param)
        logger.info(f"Resultado: {resultado}")
        return resultado
    except Exception as e:
        logger.error(f"Erro na tool: {e}")
        raise RetryAgentRun(f"Erro: {e}. Tente novamente.")
```

### Logs Úteis

```python
# Habilitar logs detalhados
import logging
logging.basicConfig(level=logging.DEBUG)

# Log específico do Agno
logging.getLogger("agno").setLevel(logging.DEBUG)

# Em desenvolvimento
agent = Agent(
    debug_mode=True,
    show_tool_calls=True,
)
```

### Verificando Configuração

```python
from app.config import settings

print(f"MODULE_ID: {settings.MODULE_ID}")
print(f"AUTH_ENABLED: {settings.AUTH_ENABLED}")
print(f"POSTGRES_URL: {'OK' if settings.POSTGRES_URL else 'Não configurado'}")
print(f"ANTHROPIC_API_KEY: {'OK' if settings.ANTHROPIC_API_KEY else 'Não configurado'}")
```

### Testando Conexão com Banco

```python
from app.storage import get_postgres_db

db = get_postgres_db()
if db:
    try:
        db.create_tables()
        print("Conexão OK")
    except Exception as e:
        print(f"Erro: {e}")
else:
    print("POSTGRES_URL não configurado")
```

---

## Debugging e Observabilidade

### Debug Mode

```python
from agno.agent import Agent

# Habilitar debug detalhado
agent = Agent(
    debug_mode=True,       # Logs detalhados do agente
    show_tool_calls=True,  # Mostra chamadas de tools
)

# Em times
from agno.team import Team

team = Team(
    debug_mode=True,
    show_members_responses=True,  # Mostra respostas de membros
)
```

### Integração Langfuse

```python
# app/langfuse_client.py
from langfuse import Langfuse
from app.config import settings

langfuse = None
if settings.LANGFUSE_ENABLED:
    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_BASE_URL,
    )


def create_trace(name: str, session_id: str, user_id: str = None):
    """Cria trace no Langfuse para observabilidade."""
    if not langfuse:
        return None

    return langfuse.trace(
        name=name,
        session_id=session_id,
        user_id=user_id,
    )


def log_tool_call(trace, tool_name: str, args: dict, result: str):
    """Registra chamada de tool no trace."""
    if trace:
        span = trace.span(
            name=f"tool:{tool_name}",
            input=args,
        )
        span.end(output=result)
```

### Métricas e Logs Estruturados

```python
import logging
from agno.utils.log import logger
import structlog

# Configurar logging básico
logging.basicConfig(level=logging.INFO)

# Log específico do Agno
logging.getLogger("agno").setLevel(logging.DEBUG)

# Logs estruturados com structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

log = structlog.get_logger()

# Uso
log.info(
    "request_processed",
    conversation_id=conversation_id,
    latency_ms=latency_ms,
    tokens_used=tokens_used,
)
```

---

## Padrões de Arquitetura

### Agente Singleton

```python
# app/agent.py
from functools import lru_cache
from agno.agent import Agent


@lru_cache(maxsize=1)
def get_base_agent() -> Agent:
    """Retorna instância singleton do agente base."""
    return Agent(
        model=get_model(),
        tools=get_tools(),
        instructions=get_instructions(),
    )


def create_session_agent(session_id: str, user_id: str) -> Agent:
    """Cria agente com contexto de sessão."""
    base = get_base_agent()
    return Agent(
        model=base.model,
        tools=base.tools,
        instructions=base.instructions,
        session_id=session_id,
        user_id=user_id,
        db=get_postgres_db(),
    )
```

### Factory Pattern para Tools

```python
# app/tools/factory.py
from typing import List, Callable


def get_tools_for_role(role: str) -> List[Callable]:
    """Retorna tools baseado no papel do usuário."""
    base_tools = [get_current_time, calculate]

    if role == "admin":
        return base_tools + [admin_action, delete_resource]
    elif role == "analyst":
        return base_tools + [query_database, generate_report]
    else:
        return base_tools


# Uso
agent = Agent(
    tools=get_tools_for_role(user_role),
)
```

### Dependency Injection Pattern

```python
# app/dependencies.py
from agno.run import RunContext


class DatabaseService:
    def query(self, sql: str) -> list:
        # Implementação
        pass


class CacheService:
    def get(self, key: str) -> any:
        pass

    def set(self, key: str, value: any, ttl: int = 3600):
        pass


def create_agent_with_services() -> Agent:
    return Agent(
        tools=[query_data, cache_result],
        dependencies={
            "db": DatabaseService(),
            "cache": CacheService(),
        },
    )


# Na tool
def query_data(run_context: RunContext, query: str) -> str:
    db = run_context.dependencies["db"]
    cache = run_context.dependencies["cache"]

    # Verifica cache
    cached = cache.get(f"query:{query}")
    if cached:
        return cached

    # Executa query
    result = db.query(query)
    cache.set(f"query:{query}", result)
    return str(result)
```

---

## Comandos Make

```bash
# Desenvolvimento
make install          # Instalar dependências de produção
make dev              # Iniciar servidor de desenvolvimento
make test             # Rodar testes
make lint             # Verificar código
make format           # Formatar código

# Docker
make docker-build     # Build da imagem
make up               # Subir serviços
make down             # Parar serviços
make logs             # Ver logs

# Migrations
make migrate          # Rodar migrations Alembic
make migrate-down     # Rollback última migration
make migrate-new      # Criar nova migration
make agno-migrate     # Criar tabelas do Agno

# Limpeza
make clean            # Remover arquivos de cache
```

---

## Checklists de Implementação

### Novo Módulo

- [ ] Definir `MODULE_ID` único
- [ ] Configurar variáveis de ambiente
- [ ] Implementar ferramentas necessárias
- [ ] Configurar instruções do agente
- [ ] Testar endpoints `/metadata`, `/run`, `/run_debug`
- [ ] Documentar ferramentas em `/metadata`
- [ ] Configurar Langfuse (opcional)
- [ ] Implementar testes automatizados

### Nova Ferramenta

- [ ] Criar função com docstring completa
- [ ] Adicionar type hints em todos os parâmetros
- [ ] Implementar tratamento de erros com `RetryAgentRun`/`StopAgentRun`
- [ ] Registrar em `app/tools/__init__.py`
- [ ] Adicionar ao agente em `app/agent.py`
- [ ] Escrever testes unitários
- [ ] Atualizar `/metadata` tools_exposed

### Knowledge Base

- [ ] Escolher backend (PgVector, LanceDb)
- [ ] Selecionar embedder apropriado
- [ ] Definir tipo de busca (vector, hybrid, keyword)
- [ ] Carregar documentos
- [ ] Testar retrieval
- [ ] Considerar reranking para maior precisão

### Multi-Agent Team

- [ ] Definir papéis claros para cada agente
- [ ] Configurar modelo apropriado
- [ ] Implementar instruções de coordenação
- [ ] Testar delegação
- [ ] Considerar histórico por membro
- [ ] Adicionar retries e backoff

---

## Referências

- [Pytest Documentation](https://docs.pytest.org)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Langfuse Documentation](https://langfuse.com/docs)
- [Structlog Documentation](https://www.structlog.org/)
