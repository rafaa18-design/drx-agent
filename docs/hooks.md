# Hooks (Pre/Post e Tool Hooks)

Hooks permitem interceptar e modificar comportamento em diferentes pontos da execução.

---

## Tipos de Hooks

| Tipo | Quando Executa | Uso |
|------|----------------|-----|
| **pre_hook** | Antes da tool ser chamada | Validação, logging |
| **post_hook** | Após a tool retornar | Transformação, auditoria |
| **tool_hooks** | Envolve toda execução de tool | Métricas, observabilidade |
| **Agent pre_hook** | Antes do agente processar | Transformação de input |
| **Agent post_hook** | Após o agente processar | Transformação de output |

---

## Pre e Post Hooks em Tools

```python
from agno.agent import Agent
from agno.tools import FunctionCall, tool


def pre_hook(fc: FunctionCall):
    """Executa ANTES da tool ser chamada."""
    print(f"[PRE] Chamando: {fc.function.name}")
    print(f"[PRE] Argumentos: {fc.arguments}")


def post_hook(fc: FunctionCall):
    """Executa APÓS a tool retornar."""
    print(f"[POST] Completou: {fc.function.name}")
    print(f"[POST] Resultado: {fc.result}")


@tool(pre_hook=pre_hook, post_hook=post_hook)
def buscar_dados(query: str) -> str:
    """Busca dados no sistema.

    Args:
        query: Termo de busca.
    """
    return f"Resultados para: {query}"


agent = Agent(tools=[buscar_dados], markdown=True)
agent.print_response("Busque informações sobre Python", stream=True)
```

---

## Tool Hooks no Agente

```python
import time
from typing import Any, Callable, Dict
from agno.agent import Agent
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.utils.log import logger


def logger_hook(
    function_name: str,
    function_call: Callable,
    arguments: Dict[str, Any]
):
    """Hook que envolve toda execução de tool."""
    # Detectar delegação em times
    if function_name == "delegate_task_to_member":
        member_id = arguments.get("member_id")
        logger.info(f"Delegando tarefa para: {member_id}")

    # Medir tempo de execução
    start_time = time.time()
    result = function_call(**arguments)
    duration = time.time() - start_time

    logger.info(f"Tool {function_name} executou em {duration:.2f}s")
    return result


agent = Agent(
    tools=[DuckDuckGoTools()],
    tool_hooks=[logger_hook],
    markdown=True,
)
```

---

## Pre-Hook de Transformação de Input

```python
from typing import Optional
from agno.agent import Agent
from agno.run.agent import RunInput
from agno.session.agent import AgentSession


def transform_input(
    run_input: RunInput,
    session: AgentSession,
    user_id: Optional[str] = None,
    debug_mode: Optional[bool] = None,
) -> None:
    """Pre-hook: Transforma o input antes do agente processar."""
    transformer = Agent(
        name="Transformador",
        instructions=["Reescreva o pedido para ser mais claro e específico."],
    )

    result = transformer.run(
        f"Transforme este pedido: '{run_input.input_content}'"
    )

    # Sobrescreve o input original
    run_input.input_content = result.content


agent = Agent(
    pre_hook=transform_input,
    instructions=["Você é um assistente de investimentos."],
)
```

---

## Hooks em Times

```python
from agno.team import Team

# Hooks aplicados a todas as tools do time e seus membros
team = Team(
    members=[agent1, agent2],
    tool_hooks=[logger_hook],
)
```

---

## Referências

- [Agno Hooks](https://docs.agno.com/tools/hooks)
