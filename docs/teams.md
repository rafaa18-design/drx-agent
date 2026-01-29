# Multi-Agent Teams

Teams permitem coordenar múltiplos agentes especializados para tarefas complexas.

---

## Conceitos de Teams

| Conceito | Descrição |
|----------|-----------|
| **Team** | Coordenador que gerencia múltiplos agentes |
| **Members** | Agentes especializados no time |
| **Delegation** | Roteamento de tarefas para membros |
| **respond_directly** | Retorna resposta do membro diretamente |
| **determine_input_for_members** | Líder sintetiza input para membros |

---

## Time Básico com Delegação

```python
from agno.agent import Agent
from agno.team import Team
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

# Criar agentes especializados
pesquisador = Agent(
    id="pesquisador",
    name="Agente Pesquisador",
    role="Pesquisa informações na web e fornece resumos factuais",
    tools=[DuckDuckGoTools()],
)

redator = Agent(
    id="redator",
    name="Agente Redator",
    role="Escreve conteúdo claro e engajante baseado em pesquisas",
)

analista = Agent(
    id="analista",
    name="Analista de Dados",
    role="Analisa dados e fornece insights com recomendações",
)

# Criar time
time_conteudo = Team(
    name="Time de Criação de Conteúdo",
    model=OpenAIChat(id="gpt-4o"),
    members=[pesquisador, redator, analista],
    instructions=[
        "Coordene os membros para criar conteúdo abrangente.",
        "Delegue pesquisa ao pesquisador, redação ao redator, análise ao analista.",
    ],
    show_members_responses=True,
)

time_conteudo.print_response(
    "Crie um relatório sobre tendências de IA em 2024",
    stream=True,
)
```

---

## Modos de Operação

```python
# === COORDINATE (Padrão) ===
# Líder sintetiza input e processa respostas dos membros
team = Team(members=[agent1, agent2])

# === ROUTE (Passthrough) ===
# Líder apenas roteia, retorna resposta direta do membro
team = Team(
    members=[agent1, agent2],
    respond_directly=True,
    determine_input_for_members=False,
)

# === COLLABORATE ===
# Todos os membros recebem a tarefa
team = Team(
    members=[agent1, agent2],
    delegate_to_all_members=True,
)
```

---

## Time com Histórico por Membro

```python
from uuid import uuid4
from agno.db.sqlite import SqliteDb

agente_alemao = Agent(
    name="Agente Alemão",
    role="Responde perguntas em alemão",
    add_history_to_context=True,
)

agente_espanhol = Agent(
    name="Agente Espanhol",
    role="Responde perguntas em espanhol",
    add_history_to_context=True,
)

time_multilingual = Team(
    name="Time Multilíngue",
    model=OpenAIChat("gpt-4o"),
    members=[agente_alemao, agente_espanhol],
    instructions=["Delegue para o agente apropriado baseado no idioma."],
    db=SqliteDb(db_file="tmp/multilingual.db"),
    respond_directly=True,
)

session_id = f"conversa_{uuid4()}"
time_multilingual.print_response(
    "Hallo, wie geht es dir?",
    stream=True,
    session_id=session_id,
)
```

---

## Time com Retries e Backoff

```python
team = Team(
    members=[pesquisador, redator],
    retries=3,                  # Número de tentativas
    exponential_backoff=True,   # Backoff exponencial em erros
)
```

---

## Referências

- [Agno Teams](https://docs.agno.com/basics/teams/overview)
