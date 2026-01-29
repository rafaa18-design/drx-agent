# State Management (Gerenciamento de Estado)

O Agno fornece um sistema robusto de gerenciamento de estado para manter dados entre execuções do agente.

---

## Conceitos

| Conceito | Descrição |
|----------|-----------|
| **session_state** | Estado mutável por sessão, acessível via `run_context.session_state` |
| **session_id** | Identificador único da sessão/conversa |
| **user_id** | Identificador do usuário (permite múltiplos usuários) |
| **db** | Backend de persistência (PostgreSQL, SQLite) |

---

## Session State Básico

```python
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.run import RunContext


def add_item(run_context: RunContext, item: str) -> str:
    """Add an item to the shopping list."""
    run_context.session_state["shopping_list"].append(item)
    return f"Added {item}. List: {run_context.session_state['shopping_list']}"


agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=SqliteDb(db_file="tmp/state.db"),
    # Estado inicial padrão para todas as sessões
    session_state={"shopping_list": []},
    tools=[add_item],
    # Usar state nas instruções
    instructions="Shopping list: {shopping_list}",
    markdown=True,
)

# Executa e modifica o estado
agent.print_response("Add milk and eggs", stream=True)

# Verificar estado final
print(f"Final state: {agent.get_session_state()}")
# Output: {'shopping_list': ['milk', 'eggs']}
```

---

## State com PostgreSQL

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat

db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"
db = PostgresDb(db_url=db_url, session_table="sessions")

agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    instructions="User name is {user_name} and age is {age}",
    db=db,
)

# Criar sessão com estado inicial
agent.print_response(
    "What is my name?",
    session_id="user_1_session_1",
    user_id="user_1",
    session_state={"user_name": "John", "age": 30},
)

# Carregar estado existente automaticamente
agent.print_response(
    "How old am I?",
    session_id="user_1_session_1",
    user_id="user_1",
)
```

---

## Múltiplos Usuários e Sessões

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat

db = PostgresDb(db_url="postgresql+psycopg://...")

agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=db,
)

# Usuário 1, Sessão 1
agent.print_response(
    "Hello!",
    session_id="session_456",
    user_id="alice@example.com",
)

# Usuário 1, Sessão 2 (nova conversa)
agent.print_response(
    "Hi there!",
    session_id="session_789",
    user_id="alice@example.com",
)

# Usuário 2, Sessão diferente
agent.print_response(
    "Hello!",
    session_id="session_101",
    user_id="bob@example.com",
)
```

---

## Acessando State em Tools

```python
from agno.run import RunContext
from agno.tools import tool


@tool
def add_to_cart(run_context: RunContext, item: str, quantity: int = 1) -> str:
    """Add item to shopping cart."""
    cart = run_context.session_state.get("cart", [])
    cart.append({"item": item, "quantity": quantity})
    run_context.session_state["cart"] = cart
    return f"Added {quantity}x {item} to cart"


@tool
def get_cart_total(run_context: RunContext) -> str:
    """Get cart items count."""
    cart = run_context.session_state.get("cart", [])
    total = sum(item["quantity"] for item in cart)
    return f"Cart has {total} items"


@tool
def clear_cart(run_context: RunContext) -> str:
    """Clear the shopping cart."""
    run_context.session_state["cart"] = []
    return "Cart cleared"


agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=SqliteDb(db_file="tmp/shop.db"),
    session_state={"cart": []},
    tools=[add_to_cart, get_cart_total, clear_cart],
    instructions="Current cart: {cart}",
)
```

---

## State em Instruções

O Agno substitui variáveis do state nas instruções automaticamente:

```python
agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=db,
    session_state={
        "user_name": "Guest",
        "preferences": {"language": "pt-BR"},
        "cart": [],
    },
    instructions="""
    User: {user_name}
    Language preference: {preferences[language]}
    Cart items: {cart}

    Always greet the user by name.
    Respond in their preferred language.
    """,
)
```

---

## State Passado no Runtime

```python
# Passar state na execução (sobrescreve o default)
agent.print_response(
    "What's in my session?",
    session_state={"shopping_list": ["Potatoes"]},
    stream=True,
)

# State é persistido e pode ser recuperado
print(f"Stored state: {agent.get_session_state()}")

# Próxima chamada com novo state sobrescreve
agent.print_response(
    "Check my state",
    session_state={"secret_number": 42},
    stream=True,
)
```

---

## Compartilhando State Entre Agentes

```python
from uuid import uuid4
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat

db = SqliteDb(db_file="tmp/shared.db")
session_id = str(uuid4())
user_id = "john_doe@example.com"

# Agente 1 - Amigável
agent_1 = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    instructions="You are really friendly and helpful.",
    db=db,
    add_history_to_context=True,
    enable_user_memories=True,
)

# Agente 2 - Técnico
agent_2 = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    instructions="You are technical and precise.",
    db=db,
    add_history_to_context=True,
    enable_user_memories=True,
)

# Ambos compartilham a mesma sessão
agent_1.print_response(
    "Hi! My name is John.",
    session_id=session_id,
    user_id=user_id,
)

# Agent 2 tem acesso ao histórico e memórias
agent_2.print_response(
    "What is my name?",
    session_id=session_id,
    user_id=user_id,
)
```

---

## State em Teams

```python
from agno.team import Team
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat

db = PostgresDb(db_url="postgresql+psycopg://...")

team = Team(
    db=db,
    model=OpenAIChat(id="gpt-4o-mini"),
    members=[researcher, writer],
    instructions="User name is {user_name} and preferences: {preferences}",
)

# Criar sessão com state
team.print_response(
    "What is my name?",
    session_id="team_session_1",
    user_id="user_1",
    session_state={"user_name": "John", "preferences": {"style": "casual"}},
)

# Carregar state existente
team.print_response(
    "Remember my preferences?",
    session_id="team_session_1",
    user_id="user_1",
)
```

---

## Session IDs Automáticos

```python
# Se não fornecer session_id, o Agno gera um UUID automaticamente
agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    db=db,
)

# Primeira execução - cria nova sessão
response = agent.run("Hello!")
print(f"Session ID: {response.session_id}")  # UUID gerado

# Para continuar a mesma sessão, use o mesmo session_id
agent.run("Continue our chat", session_id=response.session_id)
```

---

## Boas Práticas

| Prática | Descrição |
|---------|-----------|
| **Inicialize defaults** | Sempre defina `session_state` com valores padrão |
| **Use get()** | Acesse state com `.get()` para evitar KeyError |
| **Valide tipos** | O state pode ser modificado por tools, valide antes de usar |
| **Limpe dados sensíveis** | Não persista senhas ou tokens no state |
| **Use IDs consistentes** | Mantenha padrão para session_id e user_id |

---

## Referências

- [Agno State Management](https://docs.agno.com/basics/state/overview)
- [Agno Sessions](https://docs.agno.com/basics/sessions/session-management)
