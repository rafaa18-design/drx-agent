# Tools (Ferramentas)

Este documento cobre a criação de ferramentas, saída estruturada e tratamento de erros usando as exceptions do Agno.

---

## Estrutura Básica

Ferramentas são funções Python com docstrings que o LLM pode chamar:

```python
# app/tools/__init__.py

def minha_ferramenta(parametro: str) -> str:
    """Descrição curta da ferramenta para o LLM.

    Args:
        parametro (str): Descrição do parâmetro.

    Returns:
        str: Descrição do retorno.
    """
    return f"Resultado: {parametro}"
```

---

## Com Decorator @tool

Use o decorator para opções avançadas:

```python
from agno.tools import tool

@tool(stop_after_tool_call=True)  # Para execução após chamar
def buscar_clima(cidade: str) -> str:
    """Busca o clima atual de uma cidade.

    Args:
        cidade (str): Nome da cidade.
    """
    return f"O clima em {cidade} está ensolarado, 25°C."
```

---

## Acessando RunContext

Para acessar estado da sessão e dependências:

```python
from agno.run import RunContext

def adicionar_item(run_context: RunContext, item: str) -> str:
    """Adiciona item à lista de compras.

    Args:
        item (str): Item para adicionar.
    """
    if "lista" not in run_context.session_state:
        run_context.session_state["lista"] = []

    run_context.session_state["lista"].append(item)
    return f"'{item}' adicionado. Lista: {run_context.session_state['lista']}"


def obter_perfil_usuario(run_context: RunContext) -> str:
    """Obtém o perfil do usuário atual."""
    user_id = run_context.user_id
    profiles = run_context.dependencies.get("user_profiles", {})
    return profiles.get(user_id, "Perfil não encontrado")
```

---

## Registrando Ferramentas

```python
# app/agent.py
from app.tools import minha_ferramenta, buscar_clima, adicionar_item

def create_agent(...) -> Agent:
    return Agent(
        model=get_model(model_id),
        tools=[
            minha_ferramenta,
            buscar_clima,
            adicionar_item,
        ],
    )
```

---

## Toolkits Pré-construídos

```python
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from agno.tools.newspaper4k import Newspaper4kTools

agent = Agent(
    tools=[
        DuckDuckGoTools(),      # Busca web
        YFinanceTools(),        # Dados financeiros
        Newspaper4kTools(),     # Extração de artigos
    ],
)
```

---

## Structured Output (Saída Estruturada)

### Definindo Schema com Pydantic

```python
from pydantic import BaseModel, Field
from typing import List

class AnaliseCliente(BaseModel):
    """Schema para análise de cliente."""

    nome: str = Field(..., description="Nome do cliente")
    sentimento: str = Field(
        ...,
        description="Sentimento: positivo, neutro ou negativo"
    )
    problemas: List[str] = Field(
        default_factory=list,
        description="Lista de problemas identificados"
    )
    prioridade: int = Field(
        ...,
        ge=1,
        le=5,
        description="Prioridade de 1 (baixa) a 5 (alta)"
    )
```

### Usando no Agente

```python
from agno.agent import Agent, RunOutput
from agno.models.openai import OpenAIChat

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    description="Você analisa interações com clientes.",
    output_schema=AnaliseCliente,
)

response: RunOutput = agent.run("Cliente reclamou do atraso...")
analise = response.content  # Tipo: AnaliseCliente
print(f"Sentimento: {analise.sentimento}")
```

### JSON Mode vs Structured Output

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

# JSON Mode (mais flexível, menos garantido)
agent_json = Agent(
    model=OpenAIChat(id="gpt-4o"),
    output_schema=AnaliseCliente,
    use_json_mode=True,  # Usa JSON mode
)

# Structured Output (mais estrito, garantido)
agent_strict = Agent(
    model=OpenAIChat(id="gpt-4o"),
    output_schema=AnaliseCliente,
    # strict_output=True é o padrão
)

# Guided Output (menos estrito)
agent_guided = Agent(
    model=OpenAIChat(id="gpt-4o", strict_output=False),
    output_schema=AnaliseCliente,
)
```

| Modo | Descrição | Quando Usar |
|------|-----------|-------------|
| **Structured Output** | Schema estrito, garantido | Produção, dados críticos |
| **JSON Mode** | Mais flexível | Prototipagem, dados variáveis |
| **Guided Output** | Menos restrito | Quando schema é sugestão |

---

## Error Handling com Agno Exceptions

O Agno fornece duas exceptions para controlar o fluxo:

| Exception | Comportamento | Quando Usar |
|-----------|---------------|-------------|
| `RetryAgentRun` | Envia feedback ao modelo, continua execução | Validação, requisitos não atendidos |
| `StopAgentRun` | Para o loop de tool calls, finaliza run | Condição crítica atingida |

### RetryAgentRun

Permite fornecer feedback ao modelo para ajustar comportamento:

```python
from agno.exceptions import RetryAgentRun
from agno.run import RunContext

def add_item(run_context: RunContext, item: str) -> str:
    """Adiciona item à lista de compras."""
    if not run_context.session_state:
        run_context.session_state = {}

    if "shopping_list" not in run_context.session_state:
        run_context.session_state["shopping_list"] = []

    run_context.session_state["shopping_list"].append(item)
    len_shopping_list = len(run_context.session_state["shopping_list"])

    if len_shopping_list < 3:
        raise RetryAgentRun(
            f"Shopping list is: {run_context.session_state['shopping_list']}. "
            f"Minimum 3 items. Add {3 - len_shopping_list} more.",
        )

    return f"Shopping list: {run_context.session_state.get('shopping_list')}"
```

### Casos de Uso do RetryAgentRun

```python
# Validação de Input
def processar_email(run_context: RunContext, email: str) -> str:
    if "@" not in email:
        raise RetryAgentRun(
            exc="Invalid email format. Use user@domain.com",
            user_message="Por favor, forneça um email válido.",
        )
    return f"Email {email} processado"


# Requisitos de Estado
def finalizar_pedido(run_context: RunContext) -> str:
    carrinho = run_context.session_state.get("carrinho", [])
    if not carrinho:
        raise RetryAgentRun(
            exc="Cart is empty. Add items first.",
            agent_message="Attempting to add items to cart first.",
        )
    return f"Pedido finalizado: {carrinho}"


# Lógica de Negócio
def aprovar_desconto(run_context: RunContext, percentual: int) -> str:
    if percentual > 20:
        raise RetryAgentRun(
            exc=f"Discount {percentual}% exceeds 20% limit.",
        )
    return f"Desconto de {percentual}% aprovado"
```

### StopAgentRun

Para o loop de tool calls imediatamente:

```python
from agno.exceptions import StopAgentRun
from agno.run import RunContext

def check_condition(run_context: RunContext, value: int) -> str:
    """Verifica uma condição e para se atingida."""
    if value > 100:
        raise StopAgentRun(
            f"Value {value} exceeds threshold. Stopping execution."
        )
    return f"Value {value} is acceptable."
```

### Fluxo de Execução

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Run                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  LLM Call   │───▶│  Tool Call  │───▶│   Result    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         │                  │                  │             │
│         │                  ▼                  │             │
│         │         ┌───────────────┐           │             │
│         │         │ RetryAgentRun │───────────┘             │
│         │         │   (feedback)  │     (continua loop)     │
│         │         └───────────────┘                         │
│         │                  │                                 │
│         │                  ▼                                 │
│         │         ┌───────────────┐                         │
│         │         │ StopAgentRun  │──────▶ Run COMPLETED    │
│         │         │    (exit)     │                         │
│         │         └───────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

### Quando Usar Cada Exception

| Cenário | Exception | Exemplo |
|---------|-----------|---------|
| Validação falhou | `RetryAgentRun` | Email inválido |
| Pré-requisito não atendido | `RetryAgentRun` | Carrinho vazio |
| Refinamento iterativo | `RetryAgentRun` | Precisa mais dados |
| Limite crítico atingido | `StopAgentRun` | Valor excede threshold |
| Condição de parada | `StopAgentRun` | Objetivo alcançado |
| Erro irrecuperável | `StopAgentRun` | Permissão negada |

---

## Pre-hooks e Post-hooks

```python
from agno.tools import FunctionCall, tool
from agno.exceptions import RetryAgentRun

def pre_hook(fc: FunctionCall):
    """Pre-hook executado antes da tool."""
    print(f"Calling: {fc.function.name}")
    print(f"Args: {fc.arguments}")

    # Pode forçar retry
    if some_condition:
        raise RetryAgentRun("Please try again")


def post_hook(fc: FunctionCall):
    """Post-hook executado após a tool."""
    print(f"Result: {fc.result}")


@tool(pre_hook=pre_hook, post_hook=post_hook)
def minha_tool(arg: str) -> str:
    """Tool com hooks."""
    return f"Resultado: {arg}"
```

### Tool Hooks no Agente

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
    """
    Hook que envolve toda execução de tool.
    Útil para logging, métricas, e observabilidade.
    """
    # Detectar delegação em times
    if function_name == "delegate_task_to_member":
        member_id = arguments.get("member_id")
        logger.info(f"Delegando tarefa para: {member_id}")

    # Medir tempo de execução
    start_time = time.time()
    result = function_call(**arguments)  # Executa a tool
    duration = time.time() - start_time

    logger.info(f"Tool {function_name} executou em {duration:.2f}s")
    return result


# Aplicar hook a todas as tools do agente
agent = Agent(
    tools=[DuckDuckGoTools()],
    tool_hooks=[logger_hook],  # Lista de hooks
    markdown=True,
)
```

---

## Boas Práticas para Tools

| Prática | Descrição |
|---------|-----------|
| **Docstring completa** | O LLM usa para entender quando usar a tool |
| **Type hints** | Obrigatórios - definem schema de parâmetros |
| **Retorne strings** | Mais fácil para o LLM processar |
| **Trate erros** | Use `RetryAgentRun` para feedback, `StopAgentRun` para parar |
| **Valide inputs** | Sempre validar antes de processar |

---

## Referências

- [Agno Tools Documentation](https://docs.agno.com/tools/overview)
- [Agno Exceptions](https://docs.agno.com/tools/exceptions)
