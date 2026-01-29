# Few-Shot Learning

Few-shot learning permite ensinar padrões de resposta ao agente através de exemplos.

---

## Conceito

Few-shot learning usa o parâmetro `additional_input` para fornecer exemplos de conversas que demonstram o comportamento desejado. O agente aprende padrões de resposta a partir desses exemplos.

---

## Exemplos com Message

```python
from agno.agent import Agent
from agno.models.message import Message
from agno.models.openai import OpenAIChat

# Exemplos de suporte ao cliente
support_examples = [
    # Exemplo 1: Reset de senha
    Message(role="user", content="Esqueci minha senha e não consigo entrar"),
    Message(
        role="assistant",
        content="""
Vou ajudá-lo a redefinir sua senha imediatamente.

**Passos para Redefinir:**
1. Vá para a página de login e clique em "Esqueci a Senha"
2. Digite seu email
3. Verifique sua caixa de entrada (e spam)
4. Clique no link de redefinição
5. Crie uma nova senha forte

Se não receber o email em 5 minutos, verifique a pasta de spam.
Posso ajudar com mais alguma coisa?
        """.strip(),
    ),

    # Exemplo 2: Problema de cobrança
    Message(
        role="user",
        content="Fui cobrado duas vezes pelo mesmo pedido!",
    ),
    Message(
        role="assistant",
        content="""
Peço sinceras desculpas pelo erro de cobrança.

**Plano de Ação Imediato:**
1. Vou investigar sua conta para confirmar a cobrança duplicada
2. Processar reembolso completo da transação duplicada
3. Verificar configurações de pagamento
4. Fornecer número de confirmação do reembolso

O reembolso aparece em 3-5 dias úteis. Como desculpas, ofereço 10% de desconto no próximo pedido.

Posso ajudar com mais alguma coisa?
        """.strip(),
    ),

    # Exemplo 3: Problema técnico
    Message(
        role="user",
        content="O app trava quando tento fazer upload de fotos",
    ),
    Message(
        role="assistant",
        content="""
Lamento que esteja tendo problemas. Vou ajudá-lo a resolver.

**Passos de Diagnóstico:**
1. **Versão do App:** Verifique se está atualizado
2. **Reiniciar:** Feche e reabra o aplicativo
3. **Armazenamento:** Confirme que tem pelo menos 1GB livre
4. **Tamanho:** Tente fotos menores (menos de 10MB)
5. **Conexão:** Verifique sua internet

**Se persistir:**
- Tente uma foto por vez
- Limpe o cache do app
- Reinicie o dispositivo

Se nada funcionar, me informe o modelo do dispositivo e versão do sistema.
        """.strip(),
    ),
]

# Criar agente com few-shot learning
agent = Agent(
    name="Especialista de Suporte",
    model=OpenAIChat(id="gpt-4o"),
    additional_input=support_examples,  # Exemplos de aprendizado
    instructions=[
        "Você é um especialista em suporte ao cliente.",
        "Seja empático, profissional e focado em soluções.",
        "Forneça passos claros e acionáveis.",
        "Siga os padrões estabelecidos nos exemplos.",
    ],
    markdown=True,
)

# Testar com novos cenários
agent.print_response("Não encontro o email de confirmação do meu pedido")
```

---

## Few-Shot com Structured Output

```python
from pydantic import BaseModel, Field
from typing import List


class AnaliseCliente(BaseModel):
    """Schema para análise de sentimento."""
    sentimento: str = Field(description="positivo, neutro ou negativo")
    confianca: float = Field(ge=0, le=1, description="Confiança de 0 a 1")
    topicos: List[str] = Field(description="Tópicos identificados")
    acao_recomendada: str = Field(description="Próxima ação sugerida")


# Exemplos estruturados
exemplos = """
Exemplos de análise:

Input: "Adorei o produto! Chegou antes do prazo e a qualidade é incrível!"
Output: {"sentimento": "positivo", "confianca": 0.95, "topicos": ["entrega", "qualidade"], "acao_recomendada": "Solicitar avaliação pública"}

Input: "Péssimo atendimento, esperei 2 horas e ninguém resolveu"
Output: {"sentimento": "negativo", "confianca": 0.92, "topicos": ["atendimento", "tempo de espera"], "acao_recomendada": "Escalar para supervisor"}

Input: "O produto é ok, faz o que promete"
Output: {"sentimento": "neutro", "confianca": 0.75, "topicos": ["produto"], "acao_recomendada": "Perguntar sobre melhorias desejadas"}
"""

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    output_schema=AnaliseCliente,
    additional_input=exemplos,
    instructions=["Analise o sentimento do cliente seguindo os padrões."],
)

response = agent.run("O serviço foi excelente, mas o preço está alto")
print(f"Sentimento: {response.content.sentimento}")
print(f"Confiança: {response.content.confianca}")
```

---

## Few-Shot em Teams

```python
from agno.team import Team

# Exemplos para time de suporte
team_examples = [
    Message(role="user", content="Não consigo acessar minha conta"),
    Message(
        role="assistant",
        content="""
**Transferindo para Especialista de Suporte:**
- Problema de acesso à conta
- Verificar identidade
- Resolver bloqueio ou reset de senha
        """.strip(),
    ),
]

support_agent = Agent(
    name="Especialista de Suporte",
    role="Resolver problemas de acesso",
)

escalation_agent = Agent(
    name="Gerente de Escalação",
    role="Tratar casos complexos",
)

team = Team(
    name="Time de Suporte",
    members=[support_agent, escalation_agent],
    model=OpenAIChat(id="gpt-4o"),
    additional_input=team_examples,
    instructions=[
        "Coordene o suporte com excelência.",
        "Siga os padrões estabelecidos.",
    ],
)
```

---

## Boas Práticas

| Prática | Descrição |
|---------|-----------|
| **3-5 exemplos** | Quantidade ideal para a maioria dos casos |
| **Exemplos diversos** | Cubra diferentes cenários |
| **Formato consistente** | Mantenha estrutura similar nos exemplos |
| **Exemplos realistas** | Use casos reais ou muito próximos |
| **Atualize regularmente** | Melhore exemplos com base em feedback |

---

## Referências

- [Agno Context](https://docs.agno.com/basics/context/agent/overview)
