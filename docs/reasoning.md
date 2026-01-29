# Reasoning (Raciocínio)

O Agno oferece múltiplas formas de habilitar raciocínio estruturado nos agentes.

---

## Opções de Reasoning

| Método | Descrição | Quando Usar |
|--------|-----------|-------------|
| `reasoning=True` | Chain-of-thought automático | Tarefas complexas gerais |
| `ReasoningTools` | Tools explícitas think/analyze | Visibilidade do processo |
| `thinking_budget` | Controle de tokens de raciocínio | Modelos com extended thinking |

---

## Reasoning Agent (Chain-of-Thought Automático)

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

agente_raciocinio = Agent(
    model=OpenAIChat(id="gpt-4o"),
    reasoning=True,  # Habilita chain-of-thought estruturado
    markdown=True,
)

agente_raciocinio.print_response(
    "Resolva o dilema do bonde. Avalie múltiplos frameworks éticos.",
    stream=True,
    show_full_reasoning=True,  # Mostra processo de raciocínio
)
```

---

## ReasoningTools (Raciocínio Explícito)

```python
from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.tools.reasoning import ReasoningTools

agente = Agent(
    model=Claude(id="claude-sonnet-4-20250514"),
    tools=[
        ReasoningTools(add_instructions=True),  # Adiciona think() e analyze()
    ],
    instructions=["Use tabelas quando possível"],
    markdown=True,
)

agente.print_response(
    "Qual é maior: 9.11 ou 9.9? Explique seu raciocínio.",
    stream=True,
)
```

---

## Extended Thinking (Gemini)

```python
from agno.agent import Agent
from agno.models.google import Gemini

agente = Agent(
    model=Gemini(
        id="gemini-2.5-pro",
        thinking_budget=1280,      # Tokens para raciocínio interno
        include_thoughts=True,     # Inclui pensamentos na resposta
    ),
    markdown=True,
)

# Alternativa com thinking_level
agente_simples = Agent(
    model=Gemini(
        id="gemini-3-pro-preview",
        thinking_level="high",  # "low" ou "high"
    ),
)
```

---

## Custom Reasoning Agent

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

custom_reasoning_agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    instructions=[
        "Foque em rigor matemático",
        "Sempre forneça provas passo-a-passo",
    ],
)

main_agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    reasoning=True,
    reasoning_agent=custom_reasoning_agent,  # Agente de raciocínio customizado
)
```

---

## Combinando Reasoning com Tools

```python
from agno.tools.reasoning import ReasoningTools
from agno.tools.yfinance import YFinanceTools

agente_financeiro = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[
        ReasoningTools(add_instructions=True),
        YFinanceTools(),
    ],
    instructions=[
        "Analise cuidadosamente antes de recomendar.",
        "Sempre mostre o raciocínio por trás das decisões.",
    ],
)

agente_financeiro.print_response(
    "Devo investir em NVDA ou AMD? Analise os fundamentos.",
    stream=True,
    show_full_reasoning=True,
)
```

---

## Referências

- [Agno Reasoning](https://docs.agno.com/basics/reasoning/overview)
