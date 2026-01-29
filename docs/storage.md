# Storage, Estado e Memória

Este documento cobre session state, memórias de usuário, histórico de conversas e backends de armazenamento.

---

## Session State

### Inicialização

```python
agent = Agent(
    session_state={
        "carrinho": [],
        "preferencias": {},
        "historico_busca": [],
    },
)

# Acessar estado atual
estado = agent.get_session_state()
```

### Em uma Tool

```python
from agno.run import RunContext

def adicionar_ao_carrinho(run_context: RunContext, produto: str) -> str:
    run_context.session_state["carrinho"].append(produto)
    return f"Adicionado: {produto}"
```

---

## Memórias de Usuário

```python
# Configuração
agent = Agent(
    enable_user_memories=True,
    add_memories_to_context=True,
    db=get_postgres_db(),
)

# Executar com user_id
agent.run("Meu nome é João e gosto de café", user_id="user_123")

# Próxima interação - agente lembra
agent.run("O que você sabe sobre mim?", user_id="user_123")
# Resposta: "Você é João e gosta de café"

# Recuperar memórias programaticamente
memories = agent.get_user_memories(user_id="user_123")
```

---

## Resumos de Sessão

```python
agent = Agent(
    enable_session_summaries=True,
    add_session_summary_to_context=True,
    db=get_postgres_db(),
)

# Após várias interações
summary = agent.get_session_summary()
print(summary.content)
```

---

## Histórico e Contexto

### Configuração de Histórico

```python
from agno.agent import Agent
from agno.db.sqlite import SqliteDb

agent = Agent(
    db=SqliteDb(db_file="tmp/agent.db"),
    add_history_to_context=True,
    num_history_runs=5,  # Últimas 5 interações
)
```

### Recuperando Mensagens

```python
# Obter todas as mensagens da sessão
messages = agent.get_session_messages()
for msg in messages:
    print(f"{msg.role}: {msg.content}")

# Obter estado da sessão
state = agent.get_session_state()
```

### Sessions e Usuários

```python
agent = Agent(
    db=db,
    session_id="sess_abc123",  # ID da conversa
    user_id="user_001",        # ID do usuário
    add_history_to_context=True,
)

# Continuar sessão existente
existing_sessions = db.get_sessions(user_id="user_001")
```

---

## Storage Backends

### Comparação

| Backend | Uso | Persistência | Performance |
|---------|-----|--------------|-------------|
| `InMemoryDb` | Desenvolvimento, testes | Não | Alta |
| `SqliteDb` | Desenvolvimento, produção leve | Sim | Média |
| `PostgresDb` | Produção | Sim | Alta |

### InMemoryDb

```python
from agno.db.in_memory import InMemoryDb

db = InMemoryDb()  # Não persiste entre restarts

agent = Agent(
    db=db,
    add_history_to_context=True,
    num_history_runs=3,
)
```

### SqliteDb

```python
from agno.db.sqlite import SqliteDb

db = SqliteDb(
    db_file="tmp/agents.db",
    session_table="sessions",
)

agent = Agent(
    db=db,
    session_id="minha_sessao",
)
```

### PostgresDb

```python
from agno.db.postgres import PostgresDb

db = PostgresDb(
    db_url="postgresql+psycopg://user:pass@host:5432/database",
    session_table="agent_sessions",
)

agent = Agent(
    db=db,
    session_id="prod_session_001",
    user_id="user_123",
)
```

### Configuração no Template

```python
# app/storage.py

from functools import lru_cache
from agno.db.postgres import PostgresDb
from app.config import settings


@lru_cache(maxsize=1)
def get_postgres_db() -> PostgresDb | None:
    """Retorna instância singleton do PostgresDb."""
    if not settings.POSTGRES_URL:
        return None

    return PostgresDb(
        db_url=settings.POSTGRES_URL,
        session_table="agent_sessions",
    )
```

### Migrações do Agno

```bash
# Criar tabelas do Agno no PostgreSQL
make agno-migrate

# Ou manualmente:
uv run python -c "
from agno.db.postgres import PostgresDb
db = PostgresDb(db_url='postgresql+psycopg://...')
db.create_tables()
"
```

---

## Referências

- [Agno Storage Documentation](https://docs.agno.com/basics/storage/overview)
- [Agno Memory](https://docs.agno.com/basics/memory/overview)
