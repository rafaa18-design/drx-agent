# Observability (Monitoramento e Tracing)

O Agno oferece suporte nativo a OpenTelemetry e integrações com diversas plataformas de observabilidade.

---

## Conceitos

| Conceito | Descrição |
|----------|-----------|
| **OpenTelemetry** | Padrão para tracing distribuído |
| **AgnoInstrumentor** | Auto-instrumentação do Agno |
| **debug_mode** | Logs detalhados durante execução |
| **Metrics** | Métricas de uso (tokens, latência) |

---

## Debug Mode

### Habilitando Debug

```python
from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.tools.hackernews import HackerNewsTools

agent = Agent(
    model=Claude(id="claude-sonnet-4-20250514"),
    tools=[HackerNewsTools()],
    instructions="Write a report on the topic.",
    markdown=True,
    debug_mode=True,  # Habilita logs detalhados
    # debug_level=2,  # Mais detalhes ainda
)

agent.print_response("Trending startups and products.")
```

### Debug por Execução

```python
# Debug apenas para uma execução específica
agent = Agent(model=OpenAIChat(id="gpt-4o-mini"))

agent.print_response(
    "Tell me a joke.",
    debug_mode=True,  # Apenas nesta execução
)
```

### Níveis de Debug

```python
# Nível 1: Informações básicas (padrão)
agent = Agent(
    model=Claude(id="claude-sonnet-4-20250514"),
    debug_mode=True,
    debug_level=1,
)

# Nível 2: Informações detalhadas
agent = Agent(
    model=Claude(id="claude-sonnet-4-20250514"),
    debug_mode=True,
    debug_level=2,
)
```

### Variável de Ambiente

```bash
# Habilita debug para todos os agentes
export AGNO_DEBUG=True
```

---

## OpenTelemetry

### Setup Básico

```python
from opentelemetry import trace as trace_api
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from openinference.instrumentation.agno import AgnoInstrumentor

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

# Configurar tracer provider
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(
    SimpleSpanProcessor(
        OTLPSpanExporter(endpoint="http://127.0.0.1:4318/v1/traces")
    )
)
trace_api.set_tracer_provider(tracer_provider)

# Instrumentar Agno
AgnoInstrumentor().instrument()

# Criar agente (traces são enviados automaticamente)
agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[DuckDuckGoTools()],
    debug_mode=True,
)

agent.print_response("What is trending on tech news?")
```

---

## Langfuse

### Via OpenInference

```python
import base64
import os

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools
from openinference.instrumentation.agno import AgnoInstrumentor
from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Autenticação Langfuse
LANGFUSE_AUTH = base64.b64encode(
    f"{os.getenv('LANGFUSE_PUBLIC_KEY')}:{os.getenv('LANGFUSE_SECRET_KEY')}".encode()
).decode()

# Configurar endpoint (US, EU ou local)
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://us.cloud.langfuse.com/api/public/otel"
os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {LANGFUSE_AUTH}"

# Setup tracer
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace_api.set_tracer_provider(tracer_provider)

# Instrumentar
AgnoInstrumentor().instrument()

# Agente com traces no Langfuse
agent = Agent(
    name="Research Agent",
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[DuckDuckGoTools()],
    debug_mode=True,
)

agent.print_response("What are the latest AI developments?")
```

---

## LangSmith

```python
import os
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools
from openinference.instrumentation.agno import AgnoInstrumentor
from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Configurar LangSmith
endpoint = "https://eu.api.smith.langchain.com/otel/v1/traces"
headers = {
    "x-api-key": os.getenv("LANGSMITH_API_KEY"),
    "Langsmith-Project": os.getenv("LANGSMITH_PROJECT"),
}

# Setup tracer
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(
    SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers))
)
trace_api.set_tracer_provider(tracer_provider)

# Instrumentar
AgnoInstrumentor().instrument()

# Agente com traces no LangSmith
agent = Agent(
    name="Stock Market Agent",
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[DuckDuckGoTools()],
    markdown=True,
    debug_mode=True,
)

agent.print_response("What is news on the stock market?")
```

---

## Logfire

```python
import os
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools
from openinference.instrumentation.agno import AgnoInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Configurar Logfire
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://logfire-eu.pydantic.dev"
os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization={os.getenv('LOGFIRE_WRITE_TOKEN')}"

# Setup tracer
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))

# Instrumentar
AgnoInstrumentor().instrument(tracer_provider=tracer_provider)

# Agente
agent = Agent(
    name="Stock Price Agent",
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[DuckDuckGoTools()],
    debug_mode=True,
)

agent.print_response("What is the current price of Tesla?")
```

---

## OpenLIT

```python
import openlit
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

# Configurar tracer customizado
trace_provider = TracerProvider()
trace_provider.add_span_processor(
    SimpleSpanProcessor(
        OTLPSpanExporter(endpoint="http://127.0.0.1:4318/v1/traces")
    )
)
trace.set_tracer_provider(trace_provider)

# Inicializar OpenLIT
openlit.init(
    tracer=trace.get_tracer(__name__),
    disable_batch=True,
)

# Agente
agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[DuckDuckGoTools()],
    markdown=True,
)

agent.print_response("What is trending on Twitter?")
```

---

## Métricas do Run

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

agent = Agent(model=OpenAIChat(id="gpt-4o-mini"))

response = agent.run("Write a short poem")

# Acessar métricas
if response.metrics:
    print(f"Duration: {response.metrics.duration:.3f}s")
    print(f"Input tokens: {response.metrics.input_tokens}")
    print(f"Output tokens: {response.metrics.output_tokens}")
    print(f"Total tokens: {response.metrics.total_tokens}")
```

---

## Response Caching

O caching pode reduzir latência e custos:

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

# Habilitar cache de respostas
agent = Agent(
    model=OpenAIChat(
        id="gpt-4o",
        cache_response=True,  # Habilita cache
    )
)

# Primeira chamada - cache miss
response1 = agent.run("What is the capital of France?")
print(f"Duration: {response1.metrics.duration:.3f}s")  # ~1-2s

# Segunda chamada idêntica - cache hit
response2 = agent.run("What is the capital of France?")
print(f"Duration: {response2.metrics.duration:.3f}s")  # ~0.001s
```

### Cache com TTL

```python
from agno.models.anthropic import Claude

agent = Agent(
    model=Claude(
        id="claude-sonnet-4-20250514",
        cache_response=True,
        cache_ttl=3600,  # Cache por 1 hora
    ),
    tools=[...],
)
```

---

## Integração com Este Template

No template, usamos Langfuse para observabilidade:

```python
# app/langfuse_client.py
from langfuse import Langfuse

client = Langfuse(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_BASE_URL,
)

# Criar trace para cada /run
trace = client.trace(
    name="agent-run",
    session_id=conversation_id,
    input=input_messages,
    tags=["production"],
)

# Após execução
trace.update(
    output=response.content,
    metadata={"tokens": response.metrics.total_tokens},
)
```

---

## Referências

- [Agno Observability](https://docs.agno.com/integrations/observability/overview)
- [Agno Debugging](https://docs.agno.com/basics/agents/debugging-agents)
- [OpenTelemetry](https://opentelemetry.io/)
