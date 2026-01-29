# AgentOS (Runtime e Recursos Avançados)

O AgentOS é o runtime do Agno para servir agentes em produção com recursos como HITL, RBAC, Background Tasks e Remote Execution.

---

## Human-in-the-Loop (HITL)

HITL permite que agentes pausem e aguardem aprovação humana antes de executar operações sensíveis.

### Conceitos HITL

| Conceito | Descrição |
|----------|-----------|
| **requires_confirmation** | Decorator que marca tool como requerendo aprovação |
| **is_paused** | Estado do run quando aguarda confirmação |
| **active_requirements** | Lista de ações pendentes de aprovação |
| **confirm()/reject()** | Métodos para aprovar ou rejeitar ação |

### Tool com Confirmação

```python
from agno.tools import tool

@tool(requires_confirmation=True)
def delete_records(table_name: str, count: int) -> str:
    """Delete records from a database table.

    Args:
        table_name: Name of the table
        count: Number of records to delete

    Returns:
        str: Confirmation message
    """
    return f"Deleted {count} records from {table_name}"


@tool(requires_confirmation=True)
def send_notification(recipient: str, message: str) -> str:
    """Send a notification to a user.

    Args:
        recipient: Email or username of the recipient
        message: Notification message

    Returns:
        str: Confirmation message
    """
    return f"Sent notification to {recipient}: {message}"
```

### Agente com HITL

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat
from agno.os import AgentOS

db = PostgresDb(db_url="postgresql+psycopg://ai:ai@localhost:5532/ai")

agent = Agent(
    name="Data Manager",
    id="data_manager",
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[delete_records, send_notification],
    instructions=["You help users manage data operations"],
    db=db,
    markdown=True,
)

agent_os = AgentOS(
    id="agentos-hitl",
    agents=[agent],
)

app = agent_os.get_app()
```

### Fluxo de Confirmação

```python
from rich.console import Console
from rich.prompt import Prompt

console = Console()

run_response = agent.run("Delete 10 records from users table")

while run_response.is_paused:
    for requirement in run_response.active_requirements:
        if requirement.needs_confirmation:
            # Mostrar detalhes da ação
            console.print(
                f"Tool [bold blue]{requirement.tool_execution.tool_name}"
                f"({requirement.tool_execution.tool_args})[/] requires confirmation."
            )

            # Pedir confirmação
            message = Prompt.ask(
                "Do you want to continue?",
                choices=["y", "n"],
                default="y"
            ).strip().lower()

            if message == "n":
                requirement.reject("Action rejected by user")
            else:
                requirement.confirm()

    # Continuar execução
    run_response = agent.continue_run(
        run_id=run_response.run_id,
        requirements=run_response.requirements,
    )
```

### HITL com Múltiplas Tools

```python
from agno.tools.wikipedia import WikipediaTools

agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[
        get_top_hackernews_stories,  # @tool(requires_confirmation=True)
        WikipediaTools(requires_confirmation_tools=["search_wikipedia"]),
    ],
    markdown=True,
    db=SqliteDb(db_file="tmp/example.db"),
)
```

---

## RBAC (Role-Based Access Control)

RBAC permite controlar acesso a agentes e recursos usando JWT com escopos.

### Escopos Disponíveis

| Escopo | Descrição |
|--------|-----------|
| `agents:read` | Listar e visualizar todos os agentes |
| `agents:write` | Criar e atualizar agentes |
| `agents:delete` | Deletar agentes |
| `agents:run` | Executar qualquer agente |
| `agents:<agent-id>:read` | Visualizar agente específico |
| `agents:<agent-id>:run` | Executar agente específico |
| `agents:*:read` | Visualizar qualquer agente (wildcard) |
| `agents:*:run` | Executar qualquer agente (wildcard) |
| `sessions:read` | Ler sessões |
| `sessions:write` | Escrever sessões |
| `agent_os:admin` | Acesso administrativo total |

### Configuração RBAC

```python
import os
from datetime import UTC, datetime, timedelta

import jwt
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat
from agno.os import AgentOS
from agno.os.config import AuthorizationConfig
from agno.tools.duckduckgo import DuckDuckGoTools

# JWT Secret (use variável de ambiente em produção)
JWT_SECRET = os.getenv("JWT_VERIFICATION_KEY", "your-secret-key-at-least-256-bits-long")

# Database
db = PostgresDb(db_url="postgresql+psycopg://ai:ai@localhost:5532/ai")

# Criar agente
research_agent = Agent(
    id="research-agent",
    name="Research Agent",
    model=OpenAIChat(id="gpt-4o"),
    db=db,
    tools=[DuckDuckGoTools()],
    add_history_to_context=True,
    markdown=True,
)

# AgentOS com RBAC
agent_os = AgentOS(
    id="my-agent-os",
    description="RBAC Protected AgentOS",
    agents=[research_agent],
    authorization=True,
    authorization_config=AuthorizationConfig(
        verification_keys=[JWT_SECRET],
        algorithm="HS256",
    ),
)

app = agent_os.get_app()
```

### Gerando Tokens JWT

```python
from datetime import UTC, datetime, timedelta
import jwt

JWT_SECRET = "your-secret-key-at-least-256-bits-long"

# Token de usuário (leitura e execução)
user_token = jwt.encode(
    {
        "sub": "user_123",
        "session_id": "session_456",
        "scopes": ["agents:read", "agents:run"],
        "exp": datetime.now(UTC) + timedelta(hours=24),
        "iat": datetime.now(UTC),
    },
    JWT_SECRET,
    algorithm="HS256",
)

# Token admin (acesso total)
admin_token = jwt.encode(
    {
        "sub": "admin_789",
        "session_id": "admin_session_123",
        "scopes": ["agent_os:admin"],
        "exp": datetime.now(UTC) + timedelta(hours=24),
        "iat": datetime.now(UTC),
    },
    JWT_SECRET,
    algorithm="HS256",
)

# Token com acesso específico
specific_token = jwt.encode(
    {
        "sub": "user_456",
        "scopes": ["agents:research-agent:run"],  # Só pode executar research-agent
        "exp": datetime.now(UTC) + timedelta(hours=24),
    },
    JWT_SECRET,
    algorithm="HS256",
)
```

### Endpoints e Escopos Necessários

| Endpoint | Método | Escopo Necessário |
|----------|--------|-------------------|
| `/agents` | GET | `agents:read` |
| `/agents/{agent_id}` | GET | `agents:read` ou `agents:<id>:read` |
| `/agents/{agent_id}/runs` | POST | `agents:run` ou `agents:<id>:run` |
| `/sessions` | GET | `sessions:read` |
| `/sessions` | POST | `sessions:write` |

---

## Background Tasks

Background Tasks permitem executar hooks de forma assíncrona sem bloquear a resposta.

### Habilitação Global

```python
from agno.os import AgentOS

agent_os = AgentOS(
    agents=[agent],
    teams=[team],
    workflows=[workflow],
    run_hooks_in_background=True,  # Todos os hooks rodam em background
)
```

### Hooks em Background

```python
import asyncio
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.os import AgentOS
from agno.run.agent import RunInput


# Pre-hook para logging
def log_request(run_input: RunInput, agent):
    """Pre-hook que roda em background antes do processamento."""
    print(f"[Background Pre-Hook] Request for agent: {agent.name}")
    print(f"[Background Pre-Hook] Input: {run_input.input_content}")


# Post-hook para analytics
async def log_analytics(run_output, agent, session):
    """Post-hook que roda em background após a resposta."""
    print(f"[Background Post-Hook] Logging for run: {run_output.run_id}")

    # Operação lenta não bloqueia resposta
    await asyncio.sleep(2)
    print("[Background Post-Hook] Analytics logged!")


# Post-hook para notificações
async def send_notification(run_output, agent):
    """Envia notificações sem bloquear."""
    print(f"[Background Post-Hook] Sending notification for: {agent.name}")
    await asyncio.sleep(3)
    print("[Background Post-Hook] Notification sent!")


# Agente com hooks
agent = Agent(
    id="background-task-agent",
    name="BackgroundTaskAgent",
    model=OpenAIChat(id="gpt-4o-mini"),
    instructions="You are a helpful assistant",
    db=SqliteDb(db_file="tmp/agent.db"),
    pre_hooks=[log_request],
    post_hooks=[log_analytics, send_notification],
    markdown=True,
)

# AgentOS com background hooks
agent_os = AgentOS(
    agents=[agent],
    run_hooks_in_background=True,
)

app = agent_os.get_app()
```

### Hook Individual em Background

```python
from agno.hooks import hook

@hook(run_in_background=True)
async def send_slack_notification(run_output, agent):
    """Apenas este hook roda em background."""
    await send_slack_message(run_output.content)


# Hooks sem decorator rodam normalmente
def sync_hook(run_output, agent):
    """Este hook bloqueia a resposta."""
    print(f"Sync hook for {agent.name}")
```

### Considerações sobre Pre-Hooks em Background

```python
# IMPORTANTE: Pre-hooks em background NÃO podem modificar run_input
# porque executam após o run já ter iniciado

# Use pre-hooks em background apenas para:
# - Logging
# - Métricas
# - Notificações

# NÃO use para:
# - Validação de input
# - Modificação de input
# - Verificações de autorização
```

---

## Remote Execution

Remote Execution permite comunicação entre instâncias AgentOS.

### RemoteAgent

```python
import asyncio
from agno.agent import RemoteAgent


async def remote_agent_example():
    """Conectar e executar agente remoto."""
    agent = RemoteAgent(
        base_url="http://localhost:7777",
        agent_id="assistant-agent",
    )

    response = await agent.arun(
        "What is the capital of France?",
        user_id="user-123",
        session_id="session-456",
    )
    print(response.content)


asyncio.run(remote_agent_example())
```

### RemoteAgent com Streaming

```python
import asyncio
from agno.agent import RemoteAgent


async def remote_streaming_example():
    """Stream de respostas de agente remoto."""
    agent = RemoteAgent(
        base_url="http://localhost:7777",
        agent_id="assistant-agent",
    )

    async for chunk in agent.arun(
        "Tell me a short story about a brave knight",
        session_id="session-456",
        user_id="user-123",
        stream=True,
    ):
        if hasattr(chunk, "content") and chunk.content:
            print(chunk.content, end="", flush=True)


asyncio.run(remote_streaming_example())
```

### RemoteTeam

```python
import asyncio
from agno.team import RemoteTeam


async def remote_team_example():
    """Conectar e executar team remoto."""
    team = RemoteTeam(
        base_url="http://localhost:7777",
        team_id="research-team",
    )

    response = await team.arun(
        "Research the latest trends in AI",
        user_id="user-123",
        session_id="session-456",
    )
    print(response.content)


asyncio.run(remote_team_example())
```

### RemoteTeam com Streaming

```python
async def remote_team_streaming():
    """Stream de respostas de team remoto."""
    team = RemoteTeam(
        base_url="http://localhost:7778",
        team_id="research-team",
    )

    async for chunk in team.arun(
        "Analyze the data on the rise of AI",
        stream=True,
    ):
        if hasattr(chunk, "content") and chunk.content:
            print(chunk.content, end="", flush=True)
```

### Expondo Agentes para Acesso Remoto

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.os import AgentOS

# Criar agente
agent = Agent(
    id="assistant-agent",
    name="Assistant",
    model=OpenAIChat(id="gpt-4o"),
)

# Expor via AgentOS
agent_os = AgentOS(
    agents=[agent],
)

app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="server:app", port=7777, reload=True)
```

### Expondo Teams para Acesso Remoto

```python
from agno.team import Team
from agno.os import AgentOS

research_team = Team(
    id="research-team",
    name="Research Team",
    members=[researcher, writer],
)

agent_os = AgentOS(
    teams=[research_team],
)

app = agent_os.get_app()
```

---

## Combinando Recursos

### AgentOS Completo

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat
from agno.os import AgentOS
from agno.os.config import AuthorizationConfig
from agno.os.interfaces.a2a import A2A
from agno.tools import tool

# Database
db = PostgresDb(db_url="postgresql+psycopg://ai:ai@localhost:5532/ai")

# Tool HITL
@tool(requires_confirmation=True)
def sensitive_operation(data: str) -> str:
    """Operação sensível que requer confirmação."""
    return f"Executed: {data}"

# Hooks
async def log_analytics(run_output, agent, session):
    print(f"Analytics for {run_output.run_id}")

# Agente
agent = Agent(
    id="production-agent",
    name="Production Agent",
    model=OpenAIChat(id="gpt-4o"),
    tools=[sensitive_operation],
    post_hooks=[log_analytics],
    db=db,
)

# AgentOS com todos os recursos
agent_os = AgentOS(
    id="production-os",
    agents=[agent],
    # RBAC
    authorization=True,
    authorization_config=AuthorizationConfig(
        verification_keys=[JWT_SECRET],
        algorithm="HS256",
    ),
    # Background Tasks
    run_hooks_in_background=True,
    # A2A Protocol
    a2a_interface=True,
)

app = agent_os.get_app()
```

---

## MCP Server

Exponha seu AgentOS como um servidor MCP (Model Context Protocol) para integração com outros sistemas.

### Habilitar MCP Server

```python
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.anthropic import Claude
from agno.os import AgentOS
from agno.tools.duckduckgo import DuckDuckGoTools

db = SqliteDb(db_file="tmp/agentos.db")

agent = Agent(
    id="web-research-agent",
    name="Web Research Agent",
    model=Claude(id="claude-sonnet-4-20250514"),
    db=db,
    tools=[DuckDuckGoTools()],
    add_history_to_context=True,
    markdown=True,
)

# Habilitar MCP Server
agent_os = AgentOS(
    description="AgentOS with MCP enabled",
    agents=[agent],
    enable_mcp_server=True,  # MCP disponível em /mcp
)

app = agent_os.get_app()

if __name__ == "__main__":
    # MCP server em http://localhost:7777/mcp
    agent_os.serve(app="mcp_example:app", port=7777)
```

### Usando o MCP Endpoint

```bash
# Executar agente via MCP
curl -X POST http://localhost:7777/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "run_agent",
    "args": {
      "agent_id": "web-research-agent",
      "message": "What is the capital of France?"
    }
  }'
```

---

## Middleware Customizado

### Rate Limiting

```python
import time
from collections import defaultdict, deque
from typing import Dict
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting por IP."""

    def __init__(self, app, requests_per_minute: int = 60, window_size: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = window_size
        self.request_history: Dict[str, deque] = defaultdict(lambda: deque())

    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        history = self.request_history[client_ip]
        while history and current_time - history[0] > self.window_size:
            history.popleft()

        if len(history) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Max {self.requests_per_minute}/min."},
            )

        history.append(current_time)
        response = await call_next(request)

        # Headers informativos
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - len(history)
        )
        return response
```

### Security Headers

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adiciona headers de segurança."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
```

### Aplicando Middleware

```python
from agno.os import AgentOS

agent_os = AgentOS(agents=[agent])
app = agent_os.get_app()

# Adicionar middleware customizado
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)
app.add_middleware(SecurityHeadersMiddleware)
```

---

## FastAPI Custom Integration

### Preservar App Base

```python
from fastapi import FastAPI
from agno.os import AgentOS

# Sua app FastAPI existente
my_app = FastAPI(title="My API")

@my_app.get("/health")
def health():
    return {"status": "ok"}

@my_app.get("/custom")
def custom_endpoint():
    return {"message": "Custom endpoint"}

# Integrar com AgentOS
agent_os = AgentOS(
    agents=[agent],
    app=my_app,
    preserve_base_app=True,  # Mantém rotas da sua app
)

app = agent_os.get_app()
# app agora tem /health, /custom E rotas do AgentOS
```

### Custom Routers

```python
from fastapi import APIRouter, FastAPI
from agno.os import AgentOS

# Router customizado
custom_router = APIRouter(prefix="/api/v1")

@custom_router.get("/status")
def get_status():
    return {"status": "running"}

# App com router
my_app = FastAPI()
my_app.include_router(custom_router)

# Integrar
agent_os = AgentOS(agents=[agent], app=my_app)
app = agent_os.get_app()
```

### Lifespan Events

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    await initialize_resources()

    yield

    # Shutdown
    print("Shutting down...")
    await cleanup_resources()


my_app = FastAPI(lifespan=lifespan)
agent_os = AgentOS(agents=[agent], app=my_app)
```

---

## Referências

- [Agno HITL](https://docs.agno.com/agent-os/usage/hitl)
- [Agno RBAC](https://docs.agno.com/agent-os/usage/rbac/basic)
- [Agno Background Tasks](https://docs.agno.com/agent-os/usage/background-hooks-global)
- [Agno Remote Execution](https://docs.agno.com/agent-os/usage/remote-execution/remote-agent)
- [Agno MCP Server](https://docs.agno.com/agent-os/mcp/mcp)
- [Agno Middleware](https://docs.agno.com/agent-os/middleware/custom)
