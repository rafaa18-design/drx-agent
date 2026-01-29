# Configuração do Agente

Este documento cobre a configuração do agente Agno, incluindo modelos, parâmetros e providers.

---

## Parâmetros Principais

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

agent = Agent(
    # === Identificação ===
    id="meu-agente",
    name="Assistente de Vendas",

    # === Modelo ===
    model=OpenAIChat(id="gpt-4o"),

    # === Instruções ===
    description="Você é um assistente de vendas especializado.",
    instructions=[
        "Seja cordial e profissional",
        "Foque em entender as necessidades do cliente",
        "Sugira produtos relevantes",
    ],

    # === Contexto ===
    additional_context="Catálogo atual: {catalogo}",
    expected_output="Resposta útil com sugestões de produtos",

    # === Ferramentas ===
    tools=[buscar_produto, verificar_estoque],

    # === Estado ===
    session_state={"carrinho": []},

    # === Formatação ===
    markdown=True,

    # === Contexto Automático ===
    add_datetime_to_context=True,
    add_name_to_context=True,

    # === Memória e Sessão ===
    enable_user_memories=True,
    enable_session_summaries=True,
    add_history_to_context=True,
    num_history_runs=10,

    # === Banco de Dados ===
    db=PostgresDb(db_url="..."),
)
```

---

## Configuração de Memória

```python
agent = Agent(
    # Habilitar memórias de usuário
    enable_user_memories=True,

    # Habilitar resumos de sessão
    enable_session_summaries=True,

    # Adicionar histórico ao contexto
    add_history_to_context=True,
    num_history_runs=5,  # Últimas 5 interações

    # Adicionar memórias ao contexto
    add_memories_to_context=True,

    # Adicionar resumo da sessão ao contexto
    add_session_summary_to_context=True,

    # Banco para persistência
    db=get_postgres_db(),
)
```

---

## Configuração de Modelos

### Parâmetros de Geração

```python
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude

# OpenAI com parâmetros de geração
model = OpenAIChat(
    id="gpt-4o",
    api_key=settings.OPENAI_API_KEY,
    temperature=0.7,          # Aleatoriedade (0.0-2.0)
    max_tokens=2048,          # Máximo de tokens
    top_p=0.9,                # Nucleus sampling
    frequency_penalty=0.0,    # Penalidade repetição
    presence_penalty=0.0,
    stop_sequences=["END"],   # Sequências de parada
    seed=42,                  # Reprodutibilidade
)

# Claude com cache de system prompt
model = Claude(
    id="claude-sonnet-4-20250514",
    api_key=settings.ANTHROPIC_API_KEY,
    cache_system_prompt=True, # Reduz custos
    temperature=0.7,
    max_tokens=4096,
)
```

### Retry e Backoff

```python
model = OpenAIChat(
    id="gpt-4o",
    retries=3,                    # Tentativas
    delay_between_retries=1,      # Delay (segundos)
    exponential_backoff=True,     # Dobra delay
)
```

---

## Modelos por Provider

### Anthropic (Direto)

```python
from agno.models.anthropic import Claude

claude = Claude(
    id="claude-sonnet-4-20250514",
    api_key=settings.ANTHROPIC_API_KEY,
)
```

### OpenAI

```python
from agno.models.openai import OpenAIChat

gpt = OpenAIChat(
    id="gpt-4o",  # ou gpt-4-turbo, gpt-4o-mini
    api_key=settings.OPENAI_API_KEY,
)
```

### Google Gemini

```python
from agno.models.google import Gemini

gemini = Gemini(
    id="gemini-1.5-flash",
    api_key=settings.GOOGLE_API_KEY,
    thinking_enabled=True,    # Extended thinking
    thinking_budget=1280,
)
```

### AWS Bedrock

```python
from agno.models.aws import AwsBedrock

bedrock = AwsBedrock(
    id="anthropic.claude-3-sonnet-20240229-v1:0",
    aws_region="us-east-1",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)
```

### Vertex AI (Google Cloud)

```python
from agno.models.vertexai.claude import Claude as VertexClaude

vertex = VertexClaude(
    id="claude-sonnet-4@20250514",  # Note o @
    project_id=settings.GOOGLE_CLOUD_PROJECT,
    region=settings.GOOGLE_CLOUD_REGION,
)
```

### Ollama (Local)

```python
from agno.models.ollama import Ollama

ollama = Ollama(
    id="llama3.2",
    host="http://localhost:11434",
)
```

---

## Factory de Modelos (Template)

```python
# app/agent.py

def get_model(model_id: str | None = None):
    """Factory para criar modelo baseado no ID."""
    model_id = model_id or settings.DEFAULT_MODEL

    # Vertex AI (IDs contêm @)
    if '@' in model_id or settings.MODEL_PROVIDER == 'vertexai':
        from agno.models.vertexai.claude import Claude as VertexClaude
        return VertexClaude(
            id=model_id,
            project_id=settings.GOOGLE_CLOUD_PROJECT,
            region=settings.GOOGLE_CLOUD_REGION,
        )

    # Anthropic Claude
    if 'claude' in model_id.lower():
        return Claude(
            id=model_id,
            api_key=settings.ANTHROPIC_API_KEY,
            cache_system_prompt=settings.CACHE_SYSTEM_PROMPT,
        )

    # OpenAI
    if 'gpt' in model_id.lower() or 'o1' in model_id.lower():
        return OpenAIChat(
            id=model_id,
            api_key=settings.OPENAI_API_KEY,
        )

    # Default
    return Claude(id=settings.DEFAULT_MODEL)
```

---

## Input/Output Multimodal

### Formatos Suportados

| Tipo | Formatos |
|------|----------|
| text | Texto plano |
| image | jpeg, jpg, png, webp |
| audio | mp3, wav, ogg |
| video | mp4, webm |
| document | pdf, txt, md, json, docx, csv |

### Processando Input Multimodal

```python
from agno.agent import Agent, Message
from agno.media import Image, Audio, File
from agno.models.openai import OpenAIChat

agent = Agent(model=OpenAIChat(id="gpt-4o"))

# Imagem de arquivo
agent.print_response(
    "Descreva esta imagem",
    images=[Image(filepath="foto.jpg")],
)

# Imagem de URL
agent.print_response(
    "O que você vê nesta imagem?",
    images=[Image(url="https://exemplo.com/foto.jpg")],
)

# Imagem com base64
agent.print_response(
    "Descreva esta imagem",
    images=[Image(content=base64_string, format="png")],
)

# Com Message object
agent.print_response(
    Message(
        role="user",
        content=[
            {"type": "text", "text": "O que há nesta imagem?"},
            {
                "type": "image_url",
                "image_url": {"url": "https://exemplo.com/foto.jpg"},
            },
        ],
    )
)
```

### Processando Áudio e Documentos

```python
from agno.media import Audio, File

# Áudio
agent.print_response(
    "Transcreva este áudio",
    audio=[Audio(content=audio_base64, format="mp3")],
)

# Documento
agent.print_response(
    "Resuma este documento",
    files=[File(content=pdf_base64, format="pdf", name="relatorio.pdf")],
)

# Múltiplas imagens
agent.run(
    "Compare estas imagens",
    images=[
        Image(filepath="antes.jpg"),
        Image(filepath="depois.jpg"),
    ],
)
```

---

## Referências

- [Agno Agent Documentation](https://docs.agno.com/agents/overview)
- [Agno Models](https://docs.agno.com/models/overview)
