# Memory (Memórias e Session Summaries)

O Agno oferece um sistema completo de memória para agentes aprenderem e lembrarem informações sobre usuários.

---

## Conceitos

| Conceito | Descrição |
|----------|-----------|
| **User Memories** | Fatos sobre usuários armazenados automaticamente |
| **Agentic Memory** | Agente controla quando criar/atualizar memórias |
| **Session Summaries** | Resumos automáticos de conversas |
| **MemoryTools** | Ferramentas para CRUD de memórias |

---

## User Memories (Automático)

O agente automaticamente extrai e armazena fatos sobre o usuário após cada interação.

```python
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat

db = SqliteDb(db_file="tmp/agent.db")

agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=db,
    enable_user_memories=True,  # Memória automática
)

# Primeira conversa - agente aprende preferências
agent.print_response(
    "My name is Sarah and I prefer vegetarian food",
    user_id="user_123",
    session_id="session_1",
)

# Nova sessão - agente lembra
agent.print_response(
    "What food should I order?",
    user_id="user_123",
    session_id="session_2",
)
# Resposta considerará que Sarah é vegetariana
```

### Recuperar Memórias

```python
# Obter memórias do usuário
memories = agent.get_user_memories(user_id="user_123")

for mem in memories:
    print(f"- {mem.memory}")
    print(f"  Topics: {mem.topics}")
```

---

## Agentic Memory (Controlado)

O agente decide quando criar, atualizar ou deletar memórias usando ferramentas.

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat

db = PostgresDb(
    db_url="postgresql+psycopg://ai:ai@localhost:5532/ai",
    memory_table="user_memories",
)

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    db=db,
    enable_agentic_memory=True,  # Agente controla memórias
    markdown=True,
)

# O agente decide o que memorizar
agent.print_response(
    "Remember that I'm allergic to nuts and I work at Acme Corp",
    user_id="user_123",
)

# Verificar memórias
memories = agent.get_user_memories(user_id="user_123")
for mem in memories:
    print(f"Memory: {mem.memory}")
```

### Diferença entre Modos

```python
# ❌ NÃO use ambos juntos - agentic desabilita automático
agent = Agent(
    db=db,
    enable_user_memories=True,
    enable_agentic_memory=True,  # Desabilita automático!
)

# ✅ Escolha um modo
# Automático - extrai fatos automaticamente
agent = Agent(db=db, enable_user_memories=True)

# OU Agentic - agente decide explicitamente
agent = Agent(db=db, enable_agentic_memory=True)
```

---

## MemoryTools

Ferramentas explícitas para gerenciar memórias com tópicos.

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat
from agno.tools.memory import MemoryTools

db = PostgresDb(db_url="postgresql+psycopg://...")

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[MemoryTools(db=db, add_instructions=True)],
    db=db,
)

# Agente pode criar memórias com tópicos
agent.print_response(
    "I prefer vegetarian recipes and I'm allergic to nuts.",
    user_id="user_123",
)
```

---

## Session Summaries

Resumos automáticos de conversas para manter contexto sem usar todos os tokens.

### Habilitar Summaries

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat

db = PostgresDb(
    db_url="postgresql+psycopg://...",
    session_table="sessions",
)

agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=db,
    enable_session_summaries=True,  # Gera resumos automáticos
)

# Conversa longa
agent.print_response(
    "Hi, my name is John and I live in New York",
    session_id="conversation_123",
)
agent.print_response(
    "I like basketball and hiking",
    session_id="conversation_123",
)

# Recuperar resumo
summary = agent.get_session_summary(session_id="conversation_123")
if summary:
    print(f"Summary: {summary.summary}")
    print(f"Topics: {summary.topics}")
```

### Usar Summary no Contexto

```python
# Sessão existente com summary
agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=db,
    session_id="conversation_123",
    add_session_summary_to_context=True,  # Adiciona summary ao contexto
)

# Agente terá contexto da conversa anterior via summary
agent.print_response("What were we discussing?")
```

### SessionSummaryManager Customizado

```python
from agno.session.summary import SessionSummaryManager
from agno.models.openai import OpenAIChat

# Manager com modelo específico
summary_manager = SessionSummaryManager(
    model=OpenAIChat(id="gpt-4o-mini"),
)

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    db=db,
    session_summary_manager=summary_manager,
)
```

---

## Session Summaries em Teams

```python
from agno.agent import Agent
from agno.team import Team
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat

db = PostgresDb(db_url="postgresql+psycopg://...")

agent = Agent(model=OpenAIChat(id="gpt-4o-mini"))

team = Team(
    model=OpenAIChat(id="gpt-4o-mini"),
    members=[agent],
    db=db,
    enable_session_summaries=True,
)

team.print_response(
    "My name is John and I need help planning a trip",
)
```

---

## Adicionar Memórias ao Contexto

```python
agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=db,
    enable_user_memories=True,
    add_memories_to_context=True,  # Inclui memórias no prompt
)
```

---

## Compartilhar Memórias Entre Agentes

```python
from uuid import uuid4
from agno.agent import Agent
from agno.db.sqlite import SqliteDb

db = SqliteDb(db_file="tmp/shared.db")
user_id = "john@example.com"

# Agente 1 - aprende sobre o usuário
agent_1 = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=db,
    enable_user_memories=True,
)

agent_1.print_response(
    "My name is John and I love hiking",
    user_id=user_id,
)

# Agente 2 - compartilha mesmas memórias
agent_2 = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=db,
    enable_user_memories=True,
)

# Agent 2 sabe sobre John
agent_2.print_response(
    "What are my hobbies?",
    user_id=user_id,
)
```

---

## Limpar Memórias

```python
# Limpar todas as memórias do banco
db.clear_memories()

# Ou via agente (se agentic memory)
agent.print_response(
    "Forget everything about me",
    user_id="user_123",
)
```

---

## Comparação de Modos

| Feature | User Memories | Agentic Memory | MemoryTools |
|---------|---------------|----------------|-------------|
| **Controle** | Automático | Agente decide | Explícito via tools |
| **Quando usar** | Sempre aprender | Seletivo | Controle total |
| **Tópicos** | Automático | Automático | Configurável |
| **CRUD** | Create only | Full CRUD | Full CRUD |
| **Token cost** | Baixo | Médio | Baixo |

---

## Boas Práticas

| Prática | Descrição |
|---------|-----------|
| **Escolha um modo** | Não misture enable_user_memories com enable_agentic_memory |
| **Use user_id** | Sempre passe user_id para isolar memórias por usuário |
| **Session summaries** | Use para conversas longas para economizar tokens |
| **Limpe periodicamente** | Remova memórias desatualizadas |

---

## Referências

- [Agno Memory](https://docs.agno.com/basics/memory/overview)
- [Agno Session Summaries](https://docs.agno.com/basics/sessions/session-summaries)
