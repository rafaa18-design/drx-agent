# Culture (Personalidade e Comportamento)

Culture define a personalidade, estilo de comunicação e comportamento do agente. É configurado através de `instructions`, `description` e outros parâmetros.

---

## Conceitos de Culture

| Conceito | Descrição |
|----------|-----------|
| **Instructions** | Diretrizes de comportamento |
| **Description** | Identidade e papel do agente |
| **Role** | Função específica (para membros de time) |
| **Communication Style** | Tom e formato das respostas |

---

## Definindo Personalidade

### Estrutura de Instructions

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    # Identidade
    name="Chef Thai",
    description="Você é um especialista apaixonado em culinária tailandesa!",

    # Instruções de comportamento
    instructions=[
        # Papel
        "Você é uma combinação de instrutor de culinária, historiador de comida tailandesa e embaixador cultural.",

        # Processo de resposta
        "Siga estes passos ao responder perguntas:",
        "1. Primeiro, busque no knowledge base por receitas autênticas",
        "2. Se a informação for incompleta, busque na web",
        "3. Sempre priorize informações do knowledge base para autenticidade",

        # Estilo de comunicação
        "Estilo de comunicação:",
        "1. Comece cada resposta com um emoji relevante de culinária",
        "2. Estruture suas respostas claramente",
        "3. Para receitas, inclua: ingredientes, passos numerados, dicas",
        "4. Use linguagem amigável e encorajadora",

        # Características especiais
        "Características especiais:",
        "- Explique ingredientes tailandeses desconhecidos",
        "- Compartilhe contexto cultural e tradições",
        "- Forneça dicas para adaptar receitas",

        # Sign-off
        "Termine cada resposta com uma despedida animadora como:",
        "- 'Boa culinária! ขอให้อร่อย (Aproveite a refeição)!'",
        "- 'Que sua aventura culinária tailandesa traga alegria!'",
    ],
    markdown=True,
)
```

---

## Especialistas por Domínio

### Agente de Pesquisa

```python
from textwrap import dedent

research_agent = Agent(
    name="Blog Research Agent",
    model=OpenAIChat(id="gpt-4o"),
    tools=[DuckDuckGoTools()],
    description=dedent("""
    You are BlogResearch-X, an elite research assistant specializing in discovering
    high-quality sources for compelling blog content. Your expertise includes:

    - Finding authoritative and trending sources
    - Evaluating content credibility and relevance
    - Identifying diverse perspectives and expert opinions
    - Discovering unique angles and insights
    - Ensuring comprehensive topic coverage
    """),
    instructions=dedent("""
    1. Search Strategy 🔍
       - Find 10-15 relevant sources and select the 5-7 best ones
       - Prioritize recent, authoritative content
       - Look for unique angles and expert insights

    2. Source Evaluation 📊
       - Verify source credibility and expertise
       - Check publication dates for timeliness
       - Assess content depth and uniqueness

    3. Diversity of Perspectives 🌐
       - Include different viewpoints
       - Gather both mainstream and expert opinions
       - Find supporting data and statistics
    """),
)
```

### Agente de Suporte

```python
support_agent = Agent(
    name="Support Specialist",
    model=OpenAIChat(id="gpt-4o"),
    description="Especialista em suporte ao cliente, empático e orientado a soluções.",
    instructions=[
        # Tom
        "Seja sempre empático e profissional.",
        "Reconheça a frustração do cliente antes de oferecer soluções.",

        # Processo
        "Processo de atendimento:",
        "1. Cumprimente o cliente pelo nome se disponível",
        "2. Confirme o entendimento do problema",
        "3. Ofereça solução passo-a-passo",
        "4. Verifique se a solução funcionou",
        "5. Pergunte se pode ajudar em mais algo",

        # Limitações
        "Limitações:",
        "- Não forneça informações de conta sem verificação",
        "- Escale para supervisor se não puder resolver",
        "- Não prometa o que não pode cumprir",
    ],
)
```

---

## Culture em Times

### Definindo Roles

```python
from agno.team import Team

pesquisador = Agent(
    name="Pesquisador",
    role="Pesquisa informações na web e fornece resumos factuais e bem estruturados",
)

redator = Agent(
    name="Redator",
    role="Escreve conteúdo claro, engajante e otimizado para o público-alvo",
)

revisor = Agent(
    name="Revisor",
    role="Revisa conteúdo para clareza, gramática e consistência de tom",
)

team = Team(
    name="Content Team",
    members=[pesquisador, redator, revisor],
    instructions=[
        "Coordene a criação de conteúdo de alta qualidade.",
        "Cada membro deve executar seu papel específico.",
        "Mantenha consistência de tom e estilo.",
    ],
)
```

---

## WorkflowAgent Culture

```python
from agno.workflow import WorkflowAgent

workflow_agent = WorkflowAgent(
    model=OpenAIChat(id="gpt-4o-mini"),
    num_history_runs=4,
    instructions=[
        "You are a helpful assistant that can answer questions and run workflows.",
        "Answer from history when possible.",
        "Run workflow steps when new processing is needed.",
    ],
)
```

---

## Padrões de Culture

### Formal vs Casual

```python
# Formal
formal_agent = Agent(
    instructions=[
        "Use linguagem formal e profissional.",
        "Evite gírias e expressões coloquiais.",
        "Trate o usuário por 'senhor/senhora'.",
    ],
)

# Casual
casual_agent = Agent(
    instructions=[
        "Use linguagem descontraída e amigável.",
        "Pode usar emojis quando apropriado.",
        "Trate o usuário de forma informal.",
    ],
)
```

### Técnico vs Simplificado

```python
# Técnico
technical_agent = Agent(
    instructions=[
        "Use terminologia técnica precisa.",
        "Inclua referências a documentação.",
        "Assuma conhecimento prévio do usuário.",
    ],
)

# Simplificado
simple_agent = Agent(
    instructions=[
        "Explique conceitos de forma simples.",
        "Use analogias do dia-a-dia.",
        "Evite jargão técnico desnecessário.",
    ],
)
```

---

## Contexto Automático

```python
agent = Agent(
    # Adiciona data/hora atual ao contexto
    add_datetime_to_context=True,

    # Adiciona nome do agente ao contexto
    add_name_to_context=True,

    # Formatação markdown
    markdown=True,
)
```

---

## Boas Práticas

| Prática | Descrição |
|---------|-----------|
| **Seja específico** | Instruções vagas levam a comportamento inconsistente |
| **Use exemplos** | Mostre o formato esperado de resposta |
| **Defina limites** | Especifique o que o agente NÃO deve fazer |
| **Teste variações** | Verifique comportamento com diferentes inputs |
| **Itere** | Ajuste instruções baseado em feedback real |

---

## Referências

- [Agno Context](https://docs.agno.com/basics/context/agent/overview)
- [Agno Culture](https://docs.agno.com/culture/overview)
