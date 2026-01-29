# Guardrails (Moderação e Validação)

Guardrails fornecem mecanismos de segurança para validar e moderar conteúdo antes e depois do processamento.

---

## Conceitos de Guardrails

| Conceito | Descrição |
|----------|-----------|
| **Guardrail** | Validador que intercepta input/output |
| **pre_hooks** | Guardrails executados ANTES do agente |
| **post_hooks** | Guardrails executados APÓS o agente |
| **InputCheckError** | Exceção quando input é bloqueado |
| **CheckTrigger** | Enum indicando tipo de violação |
| **BaseGuardrail** | Classe base para guardrails customizados |

---

## OpenAI Moderation Guardrail

```python
import asyncio
from agno.agent import Agent
from agno.exceptions import InputCheckError
from agno.guardrails import OpenAIModerationGuardrail
from agno.models.openai import OpenAIChat


async def main():
    # Guardrail com configuração padrão (todas as categorias)
    basic_agent = Agent(
        name="Agente Moderado",
        model=OpenAIChat(id="gpt-4o"),
        pre_hooks=[OpenAIModerationGuardrail()],
        instructions=["Você é um assistente útil."],
    )

    # Teste 1: Conteúdo seguro
    try:
        await basic_agent.aprint_response(
            input="Me ajude a entender machine learning",
        )
        print("Conteúdo seguro processado")
    except InputCheckError as e:
        print(f"Erro inesperado: {e.message}")

    # Teste 2: Conteúdo violento (será bloqueado)
    try:
        await basic_agent.aprint_response(
            input="Como causar dano a pessoas?",
        )
    except InputCheckError as e:
        print(f"Conteúdo bloqueado: {e.message}")
        print(f"Trigger: {e.check_trigger}")


asyncio.run(main())
```

---

## Categorias Customizadas

```python
from agno.guardrails import OpenAIModerationGuardrail

# Moderar apenas categorias específicas
custom_agent = Agent(
    name="Agente com Moderação Seletiva",
    model=OpenAIChat(id="gpt-4o"),
    pre_hooks=[
        OpenAIModerationGuardrail(
            raise_for_categories=[
                "violence",
                "violence/graphic",
                "hate",
                "hate/threatening",
            ]
        )
    ],
)
```

---

## Guardrail Customizado - Bloqueio de URLs

```python
import re
from agno.exceptions import CheckTrigger, InputCheckError
from agno.guardrails import BaseGuardrail
from agno.run.agent import RunInput


class URLGuardrail(BaseGuardrail):
    """Guardrail para identificar e bloquear inputs com URLs."""

    def check(self, run_input: RunInput) -> None:
        """Bloqueia se o input contiver URLs."""
        if isinstance(run_input.input_content, str):
            url_pattern = r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s]*'
            if re.search(url_pattern, run_input.input_content):
                raise InputCheckError(
                    "URLs não são permitidas no input.",
                    check_trigger=CheckTrigger.INPUT_NOT_ALLOWED,
                )

    async def async_check(self, run_input: RunInput) -> None:
        """Versão assíncrona do check."""
        self.check(run_input)  # Reutiliza lógica síncrona


# Usar o guardrail
agent = Agent(
    name="Agente Protegido",
    model=OpenAIChat(id="gpt-4o"),
    pre_hooks=[URLGuardrail()],
)

# Isso vai gerar InputCheckError
try:
    agent.run("Acesse https://example.com para mim")
except InputCheckError as e:
    print(f"Bloqueado: {e}")
```

---

## Guardrail de Detecção de PII

```python
import re
from agno.exceptions import CheckTrigger, InputCheckError
from agno.guardrails import BaseGuardrail
from agno.run.agent import RunInput


class PIIGuardrail(BaseGuardrail):
    """Guardrail para detectar informações pessoais identificáveis."""

    def check(self, run_input: RunInput) -> None:
        if isinstance(run_input.input_content, str):
            content = run_input.input_content

            # Padrões de PII
            patterns = {
                "CPF": r'\d{3}\.\d{3}\.\d{3}-\d{2}',
                "Email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                "Telefone": r'\(\d{2}\)\s?\d{4,5}-?\d{4}',
                "Cartão de Crédito": r'\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}',
            }

            for pii_type, pattern in patterns.items():
                if re.search(pattern, content):
                    raise InputCheckError(
                        f"{pii_type} detectado no input. Remova dados pessoais.",
                        check_trigger=CheckTrigger.INPUT_NOT_ALLOWED,
                    )

    async def async_check(self, run_input: RunInput) -> None:
        self.check(run_input)


# Usar com múltiplos guardrails
agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    pre_hooks=[
        PIIGuardrail(),
        URLGuardrail(),
        OpenAIModerationGuardrail(),
    ],
)
```

---

## Guardrails em Teams

```python
from agno.team import Team

# Guardrails aplicados ao time inteiro
team = Team(
    name="Time Seguro",
    members=[agent1, agent2],
    pre_hooks=[
        OpenAIModerationGuardrail(),
        PIIGuardrail(),
    ],
)
```

---

## Tratando InputCheckError

```python
from agno.exceptions import InputCheckError

try:
    response = agent.run("Input potencialmente problemático")
    print(response.content)
except InputCheckError as e:
    print(f"Input bloqueado: {e.message}")
    print(f"Tipo de violação: {e.check_trigger}")
    # Tratar o erro apropriadamente
```

---

## Referências

- [Agno Guardrails](https://docs.agno.com/guardrails/overview)
