# Execução Assíncrona e Streaming

O Agno suporta execução assíncrona para melhor performance em aplicações web.

---

## Métodos Assíncronos

| Método | Descrição |
|--------|-----------|
| `agent.arun()` | Executa agente assincronamente |
| `agent.aprint_response()` | Executa e imprime com async |
| `team.arun()` | Executa team assincronamente |

---

## Execução Assíncrona Básica

```python
import asyncio
from agno.agent import Agent
from agno.models.openai import OpenAIChat

agent = Agent(model=OpenAIChat(id="gpt-4o"))


async def main():
    response = await agent.arun("Conte uma piada")
    print(response.content)


asyncio.run(main())
```

---

## Streaming Assíncrono

```python
import asyncio


async def streaming():
    """Streaming com async for."""
    async for chunk in agent.arun("Conte uma história", stream=True):
        print(chunk.content, end="", flush=True)


async def streaming_print():
    """Método helper para streaming."""
    await agent.aprint_response("Conte uma história", stream=True)


asyncio.run(streaming())
```

---

## Múltiplos Agentes em Paralelo

```python
import asyncio

agent1 = Agent(name="Pesquisador")
agent2 = Agent(name="Redator")


async def parallel_execution():
    """Executa múltiplos agentes em paralelo."""
    tasks = [
        agent1.arun("Pesquise sobre IA"),
        agent2.arun("Escreva sobre Python"),
    ]

    results = await asyncio.gather(*tasks)

    for i, result in enumerate(results):
        print(f"Agente {i+1}: {result.content[:100]}...")


asyncio.run(parallel_execution())
```

---

## Integração com FastAPI

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from agno.agent import Agent

app = FastAPI()
agent = Agent(model=get_model())


@app.post("/chat")
async def chat(message: str, conversation_id: str):
    """Endpoint assíncrono com agente."""
    response = await agent.arun(
        message,
        session_id=conversation_id,
    )
    return {"response": response.content}


@app.post("/chat/stream")
async def chat_stream(message: str):
    """Endpoint com streaming."""
    async def generate():
        async for chunk in agent.arun(message, stream=True):
            if chunk.content:
                yield chunk.content

    return StreamingResponse(generate(), media_type="text/plain")
```

---

## Async com Timeout

```python
import asyncio


async def with_timeout():
    """Execução com timeout."""
    try:
        response = await asyncio.wait_for(
            agent.arun("Tarefa complexa"),
            timeout=30.0,  # 30 segundos
        )
        return response.content
    except asyncio.TimeoutError:
        return "Timeout: tarefa demorou muito"
```

---

## Streaming Avançado

### Streaming com Callback

```python
from agno.agent import Agent, RunOutput

agent = Agent(model=get_model())


def on_chunk(chunk: str):
    """Callback para cada chunk."""
    print(chunk, end="", flush=True)


response = agent.run(
    "Explique machine learning",
    stream=True,
    on_stream=on_chunk,
)
```

### Streaming Async Generator

```python
async def stream_response(message: str):
    """Generator para streaming."""
    async for chunk in agent.arun(message, stream=True):
        yield chunk.content
```

### Streaming com Eventos

```python
from agno.agent import Agent

agent = Agent(
    model=get_model(),
    show_tool_calls=True,  # Mostra chamadas de tools durante streaming
)

# Streaming com visibilidade de tools
agent.print_response(
    "Busque o clima de São Paulo",
    stream=True,
)
```

---

## Referências

- [Agno Async](https://docs.agno.com/basics/async)
