# Workflows

Workflows permitem orquestrar múltiplos passos em pipelines complexos.

---

## Conceitos de Workflows

| Conceito | Descrição |
|----------|-----------|
| **Workflow** | Orquestrador de passos sequenciais |
| **Step** | Unidade de execução (agent, team, ou função) |
| **StepInput** | Entrada para um passo |
| **StepOutput** | Saída de um passo |
| **Executor** | Classe/função customizada para lógica complexa |
| **Condition** | Passo condicional baseado em avaliação |

---

## Workflow Básico com Agentes

```python
from agno.agent import Agent
from agno.workflow import Workflow, Step
from agno.db.sqlite import SqliteDb

pesquisador = Agent(
    name="Pesquisador",
    role="Pesquisa informações sobre o tópico",
)

redator = Agent(
    name="Redator",
    role="Escreve conteúdo baseado na pesquisa",
)

workflow = Workflow(
    name="Pipeline de Conteúdo",
    description="Pesquisa e cria conteúdo automaticamente",
    db=SqliteDb(
        session_table="workflow_session",
        db_file="tmp/workflow.db",
    ),
    steps=[
        Step(name="Pesquisa", agent=pesquisador),
        Step(name="Redação", agent=redator),
    ],
)

workflow.print_response(input="Tendências de IA em 2024", markdown=True)
```

---

## Executor com Função Customizada

```python
from agno.workflow import Step, StepInput, StepOutput
from agno.run import RunContext


def custom_content_planning(
    step_input: StepInput, run_context: RunContext
) -> StepOutput:
    """Função customizada para planejamento de conteúdo."""
    message = step_input.input
    previous_content = step_input.previous_step_content

    # Inicializar estado se necessário
    if "content_plans" not in run_context.session_state:
        run_context.session_state["content_plans"] = []

    if "plan_counter" not in run_context.session_state:
        run_context.session_state["plan_counter"] = 0

    # Incrementar contador
    run_context.session_state["plan_counter"] += 1
    plan_id = run_context.session_state["plan_counter"]

    try:
        # Lógica customizada
        planner = Agent(name="Planejador")
        response = planner.run(f"Crie um plano para: {message}")

        # Armazenar no estado
        plan_data = {
            "id": plan_id,
            "topic": message,
            "content": response.content,
        }
        run_context.session_state["content_plans"].append(plan_data)

        return StepOutput(content=response.content, success=True)

    except Exception as e:
        return StepOutput(
            content=f"Erro no planejamento: {str(e)}",
            success=False,
        )


# Usar executor no passo
passo_planejamento = Step(
    name="Planejamento",
    executor=custom_content_planning,
)
```

---

## Workflow com Condições

```python
from agno.workflow import Workflow, Step, Condition


def check_user_context(step_input, run_context) -> bool:
    """Verifica se usuário tem contexto anterior."""
    return run_context.session_state.get("has_been_greeted", False)


workflow = Workflow(
    name="Workflow Condicional",
    steps=[
        Condition(
            name="Verificar Novo Usuário",
            evaluator=lambda si, rc: not check_user_context(si, rc),
            steps=[
                Step(name="Saudar", agent=greeter_agent),
                Step(name="Marcar Saudação", executor=mark_as_greeted),
            ],
        ),
        Step(name="Processar Query", agent=main_agent),
    ],
    session_state={"has_been_greeted": False},
)
```

---

## Workflow Misto (Agents + Teams + Executors)

```python
from agno.team import Team

time_pesquisa = Team(
    name="Time de Pesquisa",
    members=[agent_web, agent_docs],
)

workflow = Workflow(
    name="Pipeline Completo",
    steps=[
        Step(name="Pesquisa", team=time_pesquisa),
        Step(name="Processamento", executor=processador_customizado),
        Step(name="Revisão", agent=agente_revisor),
    ],
    db=SqliteDb(db_file="tmp/workflow.db"),
)
```

---

## Referências

- [Agno Workflows](https://docs.agno.com/basics/workflows/overview)
