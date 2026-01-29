# Clients (AgentOSClient e A2AClient)

O Agno fornece clientes Python para interagir com instâncias AgentOS remotas.

---

## Conceitos

| Conceito | Descrição |
|----------|-----------|
| **AgentOSClient** | Cliente REST completo para AgentOS |
| **A2AClient** | Cliente para protocolo Agent-to-Agent |
| **Streaming** | Suporte a streaming de respostas |
| **Sessions** | Gerenciamento de sessões remotas |

---

## AgentOSClient

Cliente Python para interagir com instâncias AgentOS via REST API.

### Conexão Básica

```python
from agno.client import AgentOSClient

client = AgentOSClient(base_url="http://localhost:7777")

# Obter configuração do servidor
config = await client.aget_config()

# Executar agente
result = await client.run_agent(
    agent_id="my-agent",
    message="Hello!",
)
print(result.content)
```

### Executar Agente com Streaming

```python
from agno.client import AgentOSClient

client = AgentOSClient(base_url="http://localhost:7777")

# Streaming de resposta
async for chunk in client.run_agent_stream(
    agent_id="research-agent",
    message="Research AI trends",
    session_id="session-123",
    user_id="user-456",
):
    if chunk.content:
        print(chunk.content, end="", flush=True)
```

### Gerenciar Sessões

```python
from agno.client import AgentOSClient
from agno.schemas import SessionType

client = AgentOSClient(base_url="http://localhost:7777")

# Listar sessões
sessions = await client.get_sessions(
    user_id="user-123",
    session_type=SessionType.AGENT,
    limit=20,
)

for session in sessions.data:
    print(f"{session.session_id}: {session.session_name}")

# Obter sessão específica
session = await client.get_session(session_id="session-456")
print(session.messages)
```

### Gerenciar Memórias

```python
from agno.client import AgentOSClient

client = AgentOSClient(base_url="http://localhost:7777")

# Listar memórias do usuário
memories = await client.list_memories(
    user_id="user-123",
    topics=["preferences"],
    limit=10,
)

for mem in memories.data:
    print(f"{mem.memory_id}: {mem.memory}")

# Buscar memórias por conteúdo
memories = await client.list_memories(
    user_id="user-123",
    search_content="vegetarian",
)
```

### Gerenciar Knowledge Base

```python
from agno.client import AgentOSClient

client = AgentOSClient(base_url="http://localhost:7777")

# Listar conteúdo da knowledge base
content = await client.list_knowledge_content(limit=20)

for item in content.data:
    print(f"{item.id}: {item.name} ({item.status})")

# Buscar na knowledge base
results = await client.search_knowledge(
    query="machine learning",
    limit=5,
)
```

### Executar Team

```python
from agno.client import AgentOSClient

client = AgentOSClient(base_url="http://localhost:7777")

# Executar team
result = await client.run_team(
    team_id="research-team",
    message="Research and write about AI",
    session_id="team-session-123",
)
print(result.content)

# Com streaming
async for chunk in client.run_team_stream(
    team_id="research-team",
    message="Research AI trends",
):
    print(chunk.content, end="", flush=True)
```

### Executar Workflow

```python
from agno.client import AgentOSClient

client = AgentOSClient(base_url="http://localhost:7777")

# Executar workflow
result = await client.run_workflow(
    workflow_id="content-workflow",
    message="Create content about Python",
)
print(result.content)
```

---

## A2AClient

Cliente para protocolo Agent-to-Agent, permitindo comunicação cross-framework.

### Conexão Básica

```python
from agno.client.a2a import A2AClient

# Conectar a um agente via A2A
client = A2AClient("http://localhost:7001/a2a/agents/my-agent")

# Enviar mensagem
result = await client.send_message(message="Hello!")
print(result.content)
```

### Com Sessão

```python
from agno.client.a2a import A2AClient

client = A2AClient("http://localhost:7001/a2a/agents/assistant")

# Enviar com contexto de sessão
result = await client.send_message(
    message="What is Python?",
    session_id="session-123",
    user_id="user-456",
)
```

### Streaming via A2A

```python
from agno.client.a2a import A2AClient

client = A2AClient("http://localhost:7001/a2a/agents/research-agent")

# Stream de resposta
async for chunk in client.send_message_stream(
    message="Research AI trends",
    session_id="session-123",
):
    if hasattr(chunk, "content") and chunk.content:
        print(chunk.content, end="", flush=True)
```

---

## Comparação

| Feature | AgentOSClient | A2AClient |
|---------|---------------|-----------|
| **Protocolo** | REST API proprietário | A2A (Agent-to-Agent) |
| **Streaming** | ✅ | ✅ |
| **Sessions** | ✅ Gerenciamento completo | ✅ Básico |
| **Memories** | ✅ CRUD completo | ❌ |
| **Knowledge** | ✅ Search e CRUD | ❌ |
| **Cross-framework** | ❌ Apenas Agno | ✅ Qualquer framework |
| **Teams** | ✅ | ✅ |
| **Workflows** | ✅ | ❌ |

---

## Quando Usar

| Cenário | Cliente |
|---------|---------|
| Aplicação Agno se comunicando com AgentOS | AgentOSClient |
| Gerenciar sessões, memórias, knowledge | AgentOSClient |
| Integrar com frameworks não-Agno | A2AClient |
| Comunicação entre microserviços de agentes | A2AClient |

---

## Autenticação

### AgentOSClient com JWT

```python
from agno.client import AgentOSClient

client = AgentOSClient(
    base_url="http://localhost:7777",
    headers={"Authorization": f"Bearer {jwt_token}"},
)
```

### A2AClient com Headers

```python
from agno.client.a2a import A2AClient

client = A2AClient(
    "http://localhost:7001/a2a/agents/my-agent",
    headers={"Authorization": f"Bearer {token}"},
)
```

---

## Referências

- [AgentOS Client](https://docs.agno.com/agent-os/client/agentos-client)
- [A2A Client](https://docs.agno.com/agent-os/client/a2a-client)
