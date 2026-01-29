# Streaming e Eventos

O Agno suporta streaming de respostas e eventos granulares durante a execução.

---

## Conceitos

| Conceito | Descrição |
|----------|-----------|
| **stream** | Retorna chunks de conteúdo progressivamente |
| **stream_events** | Retorna eventos tipados (tool calls, etc.) |
| **RunEvent** | Tipos de eventos de agentes |
| **TeamRunEvent** | Tipos de eventos de teams |

---

## Streaming Básico

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

agent = Agent(model=OpenAIChat(id="gpt-4o-mini"))

# Streaming simples
for chunk in agent.run("Tell me a story", stream=True):
    if chunk.content:
        print(chunk.content, end="", flush=True)
```

### Com print_response

```python
# Helper que já faz o streaming formatado
agent.print_response("Tell me a story", stream=True)
```

---

## Eventos de Agente

```python
from agno.agent import Agent, RunEvent
from agno.models.anthropic import Claude
from agno.tools.hackernews import HackerNewsTools

agent = Agent(
    model=Claude(id="claude-sonnet-4-20250514"),
    tools=[HackerNewsTools()],
    markdown=True,
)

# Streaming com eventos tipados
stream = agent.run(
    "Trending products",
    stream=True,
    stream_events=True,  # Habilita eventos
)

for chunk in stream:
    if chunk.event == RunEvent.run_content:
        print(f"Content: {chunk.content}")
    elif chunk.event == RunEvent.tool_call_started:
        print(f"Tool started: {chunk.tool.tool_name}")
    elif chunk.event == RunEvent.tool_call_completed:
        print(f"Tool completed: {chunk.tool.tool_name}")
    elif chunk.event == RunEvent.reasoning_step:
        print(f"Reasoning: {chunk.reasoning_content}")
```

### Tipos de RunEvent

| Evento | Descrição |
|--------|-----------|
| `run_content` | Conteúdo gerado pelo modelo |
| `tool_call_started` | Tool começou a executar |
| `tool_call_completed` | Tool terminou de executar |
| `reasoning_step` | Passo de reasoning |
| `run_started` | Execução iniciada |
| `run_completed` | Execução finalizada |

---

## Eventos Tipados

```python
from typing import Iterator, List
from agno.agent import (
    Agent,
    RunContentEvent,
    RunOutputEvent,
    ToolCallStartedEvent,
    ToolCallCompletedEvent,
)
from agno.models.anthropic import Claude
from agno.tools.duckduckgo import DuckDuckGoTools

agent = Agent(
    model=Claude(id="claude-sonnet-4-20250514"),
    tools=[DuckDuckGoTools()],
    markdown=True,
)

run_response: Iterator[RunOutputEvent] = agent.run(
    "What's happening in tech news?",
    stream=True,
)

response: List[str] = []
for chunk in run_response:
    if isinstance(chunk, RunContentEvent):
        response.append(chunk.content)
    elif isinstance(chunk, ToolCallStartedEvent):
        response.append(
            f"Tool started: {chunk.tool.tool_name}({chunk.tool.tool_args})"
        )
    elif isinstance(chunk, ToolCallCompletedEvent):
        response.append(
            f"Tool completed: {chunk.tool.tool_name} -> {chunk.tool.result}"
        )

print("\n".join(response))
```

---

## Eventos de Team

```python
from agno.team import Team, TeamRunEvent
from agno.agent import Agent, RunEvent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

weather_agent = Agent(
    name="Weather Agent",
    role="Get weather information",
    tools=[DuckDuckGoTools()],
)

team = Team(
    name="Weather Team",
    members=[weather_agent],
    model=OpenAIChat(id="gpt-4o-mini"),
)

response_stream = team.run(
    "What is the weather in Tokyo?",
    stream=True,
    stream_events=True,
)

for event in response_stream:
    # Eventos do Team
    if event.event == TeamRunEvent.run_content:
        print(event.content, end="", flush=True)
    elif event.event == TeamRunEvent.tool_call_started:
        print(f"\nTeam tool call started: {event.tool.tool_name}")
    elif event.event == TeamRunEvent.tool_call_completed:
        print(f"Team tool call completed")
    elif event.event == TeamRunEvent.run_started:
        print("Team run started")
    elif event.event == TeamRunEvent.run_completed:
        print("\nTeam run completed")

    # Eventos dos membros
    elif event.event == RunEvent.tool_call_started:
        print(f"\nMember tool call: {event.tool.tool_name}")
    elif event.event == RunEvent.tool_call_completed:
        print(f"Member tool completed: {event.tool.result[:100]}...")
```

### Tipos de TeamRunEvent

| Evento | Descrição |
|--------|-----------|
| `run_content` | Conteúdo do team |
| `tool_call_started` | Tool do team iniciada |
| `tool_call_completed` | Tool do team completada |
| `run_started` | Team começou |
| `run_completed` | Team terminou |

---

## Streaming Assíncrono

```python
import asyncio
from agno.agent import Agent
from agno.models.openai import OpenAIChat

agent = Agent(model=OpenAIChat(id="gpt-4o-mini"))


async def stream_async():
    async for chunk in agent.arun("Tell me a story", stream=True):
        if chunk.content:
            print(chunk.content, end="", flush=True)


asyncio.run(stream_async())
```

### Async com Eventos

```python
async def stream_events_async():
    async for event in agent.arun(
        "Research AI trends",
        stream=True,
        stream_events=True,
    ):
        if event.event == RunEvent.run_content:
            print(event.content, end="", flush=True)
        elif event.event == RunEvent.tool_call_started:
            print(f"\n[Tool: {event.tool.tool_name}]")
```

---

## Streaming em FastAPI

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from agno.agent import Agent

app = FastAPI()
agent = Agent(model=OpenAIChat(id="gpt-4o-mini"))


@app.post("/chat/stream")
async def chat_stream(message: str):
    async def generate():
        async for chunk in agent.arun(message, stream=True):
            if chunk.content:
                yield chunk.content

    return StreamingResponse(
        generate(),
        media_type="text/plain",
    )


@app.post("/chat/events")
async def chat_events(message: str):
    async def generate():
        async for event in agent.arun(
            message,
            stream=True,
            stream_events=True,
        ):
            if event.event == RunEvent.run_content:
                yield f"data: {event.content}\n\n"
            elif event.event == RunEvent.tool_call_started:
                yield f"event: tool_start\ndata: {event.tool.tool_name}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
```

---

## Mostrar Tool Calls

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[DuckDuckGoTools()],
    show_tool_calls=True,  # Mostra chamadas durante streaming
)

# Tool calls são exibidas automaticamente
agent.print_response(
    "Search for the latest AI news",
    stream=True,
)
```

---

## Callback por Chunk

```python
from agno.agent import Agent

agent = Agent(model=OpenAIChat(id="gpt-4o-mini"))


def on_chunk(chunk: str):
    """Callback para cada chunk."""
    print(chunk, end="", flush=True)
    # Pode fazer outras coisas: logging, websocket, etc.


response = agent.run(
    "Explain machine learning",
    stream=True,
    on_stream=on_chunk,
)
```

---

## Generator para Streaming

```python
async def stream_response(message: str):
    """Generator para uso em APIs."""
    async for chunk in agent.arun(message, stream=True):
        if chunk.content:
            yield chunk.content


# Uso
async for text in stream_response("Hello"):
    print(text)
```

---

## Referências

- [Agno Streaming](https://docs.agno.com/basics/agents/running-agents)
- [Agno Events](https://docs.agno.com/basics/agents/usage/run-response-events)
