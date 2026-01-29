# Input/Output (Schemas e Validação)

O Agno suporta validação de entrada e saída estruturada usando Pydantic.

---

## Conceitos

| Conceito | Descrição |
|----------|-----------|
| **input_schema** | Schema Pydantic para validar entrada |
| **output_schema** | Schema para estruturar saída |
| **structured_outputs** | Saída estruturada nativa do modelo |
| **response_model** | Alias para output_schema |

---

## Input Schema

### Em Agentes

```python
from typing import List
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.hackernews import HackerNewsTools


class ResearchTopic(BaseModel):
    """Structured research topic with validation."""
    topic: str = Field(description="Main research topic")
    focus_areas: List[str] = Field(description="Specific areas to focus on")
    target_audience: str = Field(description="Who this research is for")
    sources_required: int = Field(default=5, ge=1, le=20)


agent = Agent(
    name="Research Agent",
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[HackerNewsTools()],
    input_schema=ResearchTopic,  # Valida entrada
)

# Passar dict que será validado
agent.print_response(
    input={
        "topic": "AI Trends",
        "focus_areas": ["LLMs", "Agents"],
        "target_audience": "Developers",
        "sources_required": 5,
    }
)

# Ou passar modelo Pydantic diretamente
agent.print_response(
    input=ResearchTopic(
        topic="AI Trends",
        focus_areas=["LLMs", "Agents"],
        target_audience="Developers",
    )
)
```

### Em Teams

```python
from agno.team import Team
from pydantic import BaseModel, Field


class ResearchProject(BaseModel):
    project_name: str = Field(description="Project name")
    research_topics: List[str] = Field(min_length=1)
    target_audience: str
    depth_level: str = Field(pattern="^(basic|intermediate|advanced)$")
    max_sources: int = Field(ge=3, le=20, default=10)


team = Team(
    name="Research Team",
    model=OpenAIChat(id="gpt-4o-mini"),
    members=[hackernews_agent, web_researcher],
    input_schema=ResearchProject,
)

team.print_response(
    input={
        "project_name": "AI Framework Comparison",
        "research_topics": ["LangChain", "CrewAI", "Agno"],
        "target_audience": "AI Engineers",
        "depth_level": "intermediate",
        "max_sources": 15,
    }
)
```

### Em Workflows

```python
from agno.workflow import Workflow
from agno.db.sqlite import SqliteDb


class ResearchRequest(BaseModel):
    topic: str = Field(description="Research topic")
    depth: int = Field(ge=1, le=10, description="Research depth")


workflow = Workflow(
    name="Research Workflow",
    db=SqliteDb(db_file="tmp/workflow.db"),
    steps=[research_step, summary_step],
    input_schema=ResearchRequest,  # Valida entrada
)

# Válido
workflow.print_response(
    input={"topic": "AI trends", "depth": 8},
    markdown=True,
)

# Inválido - vai falhar
# workflow.print_response(
#     input={"topic": 123, "depth": "high"},  # Tipos errados
# )
```

---

## Output Schema

### Estrutura de Saída

```python
from pydantic import BaseModel, Field
from typing import List
from agno.agent import Agent
from agno.models.openai import OpenAIChat


class MovieScript(BaseModel):
    """Structured movie script output."""
    title: str = Field(description="Movie title")
    genre: str = Field(description="Movie genre")
    setting: str = Field(description="Where the movie takes place")
    characters: List[str] = Field(description="Main character names")
    plot_summary: str = Field(description="Brief plot summary")


agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    description="You write movie scripts",
    output_schema=MovieScript,  # Força estrutura de saída
)

response = agent.run("Write a sci-fi movie about Mars colonization")

# Acesso tipado
script: MovieScript = response.content
print(f"Title: {script.title}")
print(f"Genre: {script.genre}")
print(f"Characters: {', '.join(script.characters)}")
```

### Análise Estruturada

```python
class StockAnalysis(BaseModel):
    symbol: str
    company_name: str
    current_price: float
    recommendation: str = Field(description="Buy, Hold, or Sell")
    reasoning: str
    risk_level: str = Field(pattern="^(low|medium|high)$")


agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    output_schema=StockAnalysis,
)

response = agent.run("Analyze Apple stock")
analysis: StockAnalysis = response.content

print(f"Recommendation: {analysis.recommendation}")
print(f"Risk: {analysis.risk_level}")
```

---

## Structured Outputs (Nativo)

Alguns modelos suportam structured outputs nativamente:

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat


class TaskList(BaseModel):
    tasks: List[str]
    priority: str
    deadline: str


agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    output_schema=TaskList,
    structured_outputs=True,  # Usa feature nativa do modelo
)
```

---

## JSON Mode

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat


class Response(BaseModel):
    answer: str
    confidence: float


agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    output_schema=Response,
    use_json_mode=True,  # Força JSON válido
    parse_response=True,  # Parseia para o modelo
)
```

---

## Parser Model

Use um modelo secundário para parsear respostas:

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat


class Summary(BaseModel):
    main_points: List[str]
    conclusion: str


agent = Agent(
    model=OpenAIChat(id="gpt-4o"),  # Modelo principal
    output_schema=Summary,
    parser_model="openai:gpt-3.5-turbo",  # Modelo para parsing
    parser_model_prompt="Extract the main points and conclusion.",
)
```

---

## Output Model

Modelo dedicado para estruturar a saída:

```python
agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    output_schema=Summary,
    output_model="openai:gpt-4o-mini",  # Modelo para output
    output_model_prompt="Format the response according to the schema.",
)
```

---

## Validação Customizada

```python
from pydantic import BaseModel, Field, field_validator


class UserInput(BaseModel):
    email: str
    age: int = Field(ge=0, le=150)
    preferences: List[str] = Field(max_length=10)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()


agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    input_schema=UserInput,
)

# Falha na validação
# agent.run(input={"email": "invalid", "age": 25, "preferences": []})
```

---

## Input e Output Juntos

```python
class QueryInput(BaseModel):
    question: str
    context: str = ""
    max_length: int = Field(default=500, le=2000)


class QueryOutput(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)
    sources: List[str] = []


agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    input_schema=QueryInput,
    output_schema=QueryOutput,
)

response = agent.run(
    input=QueryInput(
        question="What is Python?",
        context="Programming language",
        max_length=200,
    )
)

output: QueryOutput = response.content
print(f"Answer: {output.answer}")
print(f"Confidence: {output.confidence}")
```

---

## Em Teams

```python
from agno.team import Team


class TeamInput(BaseModel):
    task: str
    resources: List[str] = []


class TeamOutput(BaseModel):
    result: str
    contributors: List[str]
    time_spent: str


team = Team(
    model=OpenAIChat(id="gpt-4o"),
    members=[researcher, writer],
    input_schema=TeamInput,
    output_schema=TeamOutput,
)
```

---

## Boas Práticas

| Prática | Descrição |
|---------|-----------|
| **Use Field()** | Sempre adicione descriptions nos campos |
| **Valide ranges** | Use ge, le, min_length, max_length |
| **Defaults sensatos** | Forneça valores default quando apropriado |
| **Padrões regex** | Use pattern para strings com formato |
| **Docstrings** | Adicione docstrings nas classes |

---

## Referências

- [Agno Input/Output](https://docs.agno.com/basics/input-output/overview)
- [Agno Structured Outputs](https://docs.agno.com/basics/structured-output)
- [Pydantic Documentation](https://docs.pydantic.dev/)
