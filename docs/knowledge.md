# Knowledge Bases e RAG

O Agno suporta RAG (Retrieval-Augmented Generation) com múltiplos backends de banco de dados vetorial.

---

## Conceitos Fundamentais

| Conceito | Descrição |
|----------|-----------|
| **Knowledge** | Container para documentos e embeddings |
| **VectorDB** | Backend de armazenamento (PgVector, LanceDb, etc.) |
| **Embedder** | Modelo para gerar embeddings |
| **SearchType** | Tipo de busca (vector, hybrid, keyword) |
| **Reranker** | Re-ordenação de resultados para maior precisão |

---

## Agentic RAG vs Traditional RAG

```python
# === AGENTIC RAG (Recomendado) ===
# O agente decide quando buscar no knowledge base
agent = Agent(
    knowledge=knowledge,
    search_knowledge=True,  # Habilita tool de busca
)

# === TRADITIONAL RAG ===
# Contexto sempre adicionado ao prompt
agent = Agent(
    knowledge=knowledge,
    add_knowledge_to_context=True,
    search_knowledge=False,
)
```

---

## Configuração com PgVector (PostgreSQL)

```python
from agno.agent import Agent
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.models.openai import OpenAIChat
from agno.vectordb.pgvector import PgVector, SearchType

knowledge = Knowledge(
    vector_db=PgVector(
        table_name="documentos",
        db_url="postgresql+psycopg://user:pass@localhost:5432/db",
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
)

# Adicionar conteúdo
knowledge.add_content(url="https://exemplo.com/documento.pdf")
knowledge.add_content(text="Texto direto para indexar...")

# Criar agente com RAG
agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    knowledge=knowledge,
    search_knowledge=True,
    instructions=["Sempre cite as fontes nas respostas."],
    markdown=True,
)

agent.print_response("Explique o conceito X do documento", stream=True)
```

---

## Configuração com LanceDb (Local/Serverless)

```python
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.lancedb import LanceDb, SearchType

# LanceDb é local e não requer servidor
knowledge = Knowledge(
    vector_db=LanceDb(
        table_name="meus_documentos",
        uri="tmp/lancedb",  # Diretório local
        search_type=SearchType.vector,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
)
```

---

## Busca Híbrida com Reranking

```python
from agno.knowledge.embedder.cohere import CohereEmbedder
from agno.knowledge.reranker.cohere import CohereReranker
from agno.vectordb.lancedb import LanceDb, SearchType

knowledge = Knowledge(
    vector_db=LanceDb(
        uri="tmp/lancedb",
        table_name="docs",
        search_type=SearchType.hybrid,  # Combina vector + keyword
        embedder=CohereEmbedder(id="embed-v4.0"),
        reranker=CohereReranker(model="rerank-v3.5"),  # Re-ordena resultados
    ),
)
```

---

## Tipos de Busca

| SearchType | Descrição | Quando Usar |
|------------|-----------|-------------|
| `vector` | Busca por similaridade semântica | Perguntas conceituais |
| `keyword` | Busca por palavras-chave (BM25) | Termos específicos, nomes |
| `hybrid` | Combina vector + keyword | Melhor precisão geral |

---

## Carregamento Assíncrono

```python
import asyncio

# Carregamento assíncrono para grandes volumes
asyncio.run(
    knowledge.add_content_async(url="https://docs.agno.com/guia-completo.pdf")
)
```

---

## Filtros de Knowledge (Avançado)

### Filtros Simples (Dict)

```python
# Filtro por igualdade
agent.run(
    "Search for HR policies",
    knowledge_filters={"department": "hr"},
)

# Múltiplos filtros (AND implícito)
agent.run(
    "Find recent tech articles",
    knowledge_filters={
        "category": "technology",
        "year": 2024,
    },
)
```

### Filter Expressions (Operadores)

Para consultas complexas, use filter expressions com operadores:

```python
from agno.filters import EQ, GT, LT, IN, AND, OR, NOT
import json

# EQ - Igualdade
filter_expr = EQ("status", "published")

# GT/LT - Maior/Menor que
filter_expr = GT("views", 1000)
filter_expr = LT("price", 100)

# IN - Está na lista
filter_expr = IN("category", ["tech", "science", "ai"])

# AND - Todas condições
filter_expr = AND(
    EQ("status", "published"),
    GT("views", 1000),
)

# OR - Qualquer condição
filter_expr = OR(
    EQ("category", "tech"),
    EQ("category", "science"),
)

# NOT - Negação
filter_expr = NOT(EQ("status", "archived"))

# Serializar para API
filter_json = json.dumps(filter_expr.to_dict())
```

### Filtros em Requisições HTTP

```bash
# Via cURL
curl -X POST 'http://localhost:7777/agents/my-agent/runs' \
  -F 'message=Find tech articles' \
  -F 'knowledge_filters={"op": "EQ", "key": "category", "value": "technology"}'

# AND complexo
curl -X POST 'http://localhost:7777/agents/my-agent/runs' \
  -F 'message=Find popular tech articles' \
  -F 'knowledge_filters={
    "op": "AND",
    "conditions": [
      {"op": "EQ", "key": "category", "value": "tech"},
      {"op": "GT", "key": "views", "value": 1000}
    ]
  }'
```

### Operadores Disponíveis

| Operador | Descrição | Exemplo |
|----------|-----------|---------|
| `EQ(key, value)` | Igual a | `EQ("status", "active")` |
| `GT(key, value)` | Maior que | `GT("price", 100)` |
| `LT(key, value)` | Menor que | `LT("age", 30)` |
| `IN(key, [values])` | Está na lista | `IN("tag", ["a", "b"])` |
| `AND(*filters)` | Todas verdadeiras | `AND(f1, f2, f3)` |
| `OR(*filters)` | Alguma verdadeira | `OR(f1, f2)` |
| `NOT(filter)` | Negação | `NOT(EQ("x", "y"))` |

---

## Embedders Disponíveis

### OpenAI Embedder

```python
from agno.knowledge.embedder.openai import OpenAIEmbedder

embedder = OpenAIEmbedder(id="text-embedding-3-small")
# Ou: text-embedding-3-large, text-embedding-ada-002
```

### Cohere Embedder

```python
from agno.knowledge.embedder.cohere import CohereEmbedder

embedder = CohereEmbedder(id="embed-v4.0")
# Ou: embed-multilingual-v3.0
```

### Google Embedder

```python
from agno.knowledge.embedder.google import GeminiEmbedder

embedder = GeminiEmbedder(id="text-embedding-004")
```

### Ollama Embedder (Local)

```python
from agno.knowledge.embedder.ollama import OllamaEmbedder

embedder = OllamaEmbedder(
    id="nomic-embed-text",
    host="http://localhost:11434",
)
```

### Comparação de Embedders

| Embedder | Dimensões | Uso | Custo |
|----------|-----------|-----|-------|
| `text-embedding-3-small` | 1536 | Geral, rápido | Baixo |
| `text-embedding-3-large` | 3072 | Alta precisão | Médio |
| `embed-v4.0` | 1024 | Multilingual | Médio |
| `nomic-embed-text` | 768 | Local, privado | Gratuito |

---

## Referências

- [Agno Knowledge](https://docs.agno.com/basics/knowledge/overview)
- [Agno Embedders](https://docs.agno.com/basics/knowledge/embedders)
