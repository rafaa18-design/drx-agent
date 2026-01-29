# Integrações (MCP, Evals, A2A)

Este documento cobre integrações do Agno com protocolos e ferramentas externas.

---

## MCP (Model Context Protocol)

O MCP permite que agentes interajam com sistemas externos através de uma interface padronizada.

### Conexão Básica

```python
from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.tools.mcp import MCPTools

# Criar agente com MCP
agent = Agent(
    name="Agente MCP",
    model=Claude(id="claude-sonnet-4-20250514"),
    tools=[MCPTools(transport="streamable-http", url="https://docs.agno.com/mcp")],
)
```

### Com Gerenciamento de Conexão

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.mcp import MCPTools

# Inicializar e conectar ao servidor MCP
mcp_tools = MCPTools(url="https://docs.agno.com/mcp")
await mcp_tools.connect()

try:
    agent = Agent(model=OpenAIChat(id="gpt-4o"), tools=[mcp_tools])
    await agent.aprint_response("Busque informações sobre MCP", stream=True)
finally:
    # Sempre fechar a conexão
    await mcp_tools.close()
```

### MCP com Comando Local

```python
# Servidor MCP local via comando
mcp_tools = MCPTools(command="uvx mcp-server-git")
agent = Agent(model=OpenAIChat(id="gpt-4o"), tools=[mcp_tools])
await agent.aprint_response("Qual a licença deste projeto?", stream=True)
```

---

## Evals (Avaliações)

O Agno fornece ferramentas para avaliar a performance dos agentes.

### Conceitos de Evals

| Eval | Descrição |
|------|-----------|
| **AccuracyEval** | Mede correção comparando com resposta esperada |
| **PerformanceEval** | Mede latência e uso de memória |
| **LLM-as-judge** | Usa modelo para avaliar qualidade |

### AccuracyEval

```python
from typing import Optional
from agno.agent import Agent
from agno.eval.accuracy import AccuracyEval, AccuracyResult
from agno.models.openai import OpenAIChat
from agno.tools.calculator import CalculatorTools

# Criar avaliação de acurácia
evaluation = AccuracyEval(
    model=OpenAIChat(id="gpt-4o-mini"),
    agent=Agent(
        model=OpenAIChat(id="gpt-4o-mini"),
        tools=[CalculatorTools()],
    ),
    input="Quanto é 10*5 elevado a 2? Faça passo a passo.",
    expected_output="2500",
    additional_guidelines="Output deve incluir os passos e resposta final.",
)

# Executar avaliação
result: Optional[AccuracyResult] = evaluation.run(print_results=True)
```

### PerformanceEval

```python
from agno.eval.performance import PerformanceEval

# Avaliação de performance
perf_eval = PerformanceEval(
    agent=meu_agente,
    input="Calcule o fatorial de 10",
    num_iterations=5,  # Executa 5 vezes para média
)

perf_result = perf_eval.run(print_results=True)
print(f"Latência média: {perf_result.avg_latency_ms}ms")
print(f"Uso de memória: {perf_result.memory_mb}MB")
```

### Batch de Avaliações

```python
# Avaliar múltiplos casos
test_cases = [
    {"input": "Qual a capital do Brasil?", "expected": "Brasília"},
    {"input": "Quem escreveu Dom Casmurro?", "expected": "Machado de Assis"},
]

for case in test_cases:
    eval_result = AccuracyEval(
        model=OpenAIChat(id="gpt-4o-mini"),
        agent=meu_agente,
        input=case["input"],
        expected_output=case["expected"],
    ).run()
    print(f"Input: {case['input']}")
    print(f"Passou: {eval_result.passed}")
```

---

## A2A Protocol (Agent-to-Agent)

O protocolo A2A permite comunicação padronizada entre agentes através do AgentOS.

### Conceitos A2A

| Conceito | Descrição |
|----------|-----------|
| **A2A Interface** | Interface que expõe agentes via protocolo A2A |
| **AgentOS** | Runtime que gerencia agentes e interfaces |
| **A2AClient** | Cliente para comunicar com agentes A2A |
| **RemoteTeam** | Time que se conecta a agentes remotos |

### Setup AgentOS com A2A

```python
from agno.agent import Agent
from agno.os import AgentOS
from agno.models.openai import OpenAIChat

agent = Agent(
    name="My Agno Agent",
    id="my_agent",
    model=OpenAIChat(id="gpt-4o"),
    instructions="You are a helpful AI assistant.",
    add_datetime_to_context=True,
    markdown=True,
)

agent_os = AgentOS(
    agents=[agent],
    a2a_interface=True,  # Habilita interface A2A
)

app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="a2a:app", reload=True)
```

### A2A Interface Explícita

```python
from agno.agent import Agent
from agno.os import AgentOS
from agno.os.interfaces.a2a import A2A

agent = Agent(name="My Agno Agent", id="my_agent")

# Inicializar interface A2A especificando agentes a expor
a2a = A2A(agents=[agent])

agent_os = AgentOS(
    agents=[agent],
    interfaces=[a2a],  # Passa interface A2A para o AgentOS
)

app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="a2a-interface:app", reload=True)
```

### A2A Client

```python
from agno.client.a2a import A2AClient

# Conectar a um endpoint AgentOS A2A
client = A2AClient("http://localhost:7001/a2a/agents/my-agent")

# Enviar mensagem
result = await client.send_message(message="Hello!")
print(result.content)
```

### RemoteTeam via A2A

```python
from agno.team import RemoteTeam

team = RemoteTeam(
    base_url="http://localhost:7778/a2a/teams/my-team",
    team_id="my-team",
    protocol="a2a",
)

# Resposta única
response = await team.arun("Research the rise of AI in the last decade")
print(response.content)

# Streaming também é suportado
async for event in team.arun("Analyze the data on the rise of AI", stream=True):
    if hasattr(event, "content") and event.content:
        print(event.content, end="", flush=True)
```

### Expondo Teams via A2A

```python
from agno.team import Team
from agno.os import AgentOS
from agno.os.interfaces.a2a import A2A

research_team = Team(
    name="Research Team",
    id="research-team",
    members=[researcher, writer],
)

# Expor team via A2A
a2a = A2A(teams=[research_team])

agent_os = AgentOS(
    teams=[research_team],
    interfaces=[a2a],
)
```

---

## Referências

- [Agno MCP](https://docs.agno.com/basics/tools/mcp/overview)
- [Agno Evals](https://docs.agno.com/basics/evals/overview)
- [Agno A2A](https://docs.agno.com/agent-os/interfaces/a2a/introduction)
