# Padrão AgentBench

O **AgentBench** é um **contrato funcional interno da Asani** criado para padronizar a interface de comunicação entre módulos de agentes de IA e sistemas internos da empresa. **Não é um padrão de mercado** - é uma especificação proprietária desenvolvida pela Asani para garantir interoperabilidade entre seus sistemas.

---

## Por que o AgentBench existe?

O AgentBench foi criado para resolver um problema comum: **como diferentes sistemas internos podem se comunicar com módulos de IA de forma consistente?**

| Objetivo | Benefício |
|----------|-----------|
| **Padronizar comunicação** | Qualquer sistema interno sabe exatamente como chamar um módulo |
| **Facilitar integrações** | Novos módulos seguem o mesmo contrato, plug-and-play |
| **Garantir observabilidade** | O padrão exige métricas e trajetórias para monitoramento |
| **Permitir substituição** | Módulos podem ser trocados sem quebrar integrações |
| **Simplificar governança** | Auditoria e compliance facilitados pelo padrão único |

---

## Arquitetura do Contrato

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SISTEMAS INTERNOS ASANI                           │
│                                                                      │
│  • Chamam endpoints padronizados AgentBench                         │
│  • Recebem respostas e trajetórias em formato consistente           │
│  • NÃO interferem na execução interna do módulo                     │
│  • Coletam métricas e observabilidade                               │
│  • Autenticam via JWT                                               │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    Contrato AgentBench
                    (Interface Padronizada)
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MÓDULO DE IA                                    │
│                 (Orquestrador Soberano)                              │
│                                                                      │
│  • Gerencia seu próprio pipeline interno                            │
│  • Controla estado, memória e contexto                              │
│  • Decide quais tools usar e quando                                 │
│  • Retorna resultado final + trajetória padronizada                 │
│  • Implementa endpoints: /metadata, /run, /run_debug                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Princípios do Padrão

| Princípio | Descrição |
|-----------|-----------|
| **Soberania do Módulo** | O módulo é dono absoluto do seu pipeline interno |
| **Observabilidade** | Sistemas externos podem observar, mas não interferir |
| **Contrato Estrito** | Schemas de request/response bem definidos |
| **Autenticação JWT** | Obrigatória para todas as chamadas (exceto health) |
| **Métricas Padronizadas** | Todo `/run` retorna métricas no formato esperado |
| **Trajetória Completa** | `/run_debug` fornece trace completo da execução |

---

## Endpoints Obrigatórios

| Endpoint | Método | Auth | Descrição |
|----------|--------|------|-----------|
| `/metadata` | GET | Sim | Metadados declarativos do módulo |
| `/run` | POST | Sim | Execução em produção |
| `/run_debug` | POST | Sim | Execução com observabilidade completa |

---

## GET /metadata

Retorna informações declarativas sobre o módulo.

```json
{
  "module_id": "meu-agente",
  "version": "1.0.0",
  "description": "Descrição do módulo",
  "capabilities": {
    "supports_multi_stage": false,
    "supports_dynamic_system_prompt": true,
    "supports_cross_model": true,
    "supports_streaming": true,
    "supports_tool_calling": true,
    "supports_structured_output": true
  },
  "pipeline": {
    "is_monolithic": true,
    "stages": [
      {
        "id": "main",
        "name": "Main Agent",
        "type": "agent",
        "model": "claude-sonnet-4-20250514"
      }
    ]
  },
  "tools_exposed": [
    {
      "name": "get_current_time",
      "description": "Retorna data/hora atual",
      "parameters": {}
    }
  ],
  "input_types": {
    "supported_types": ["text", "image", "audio", "document", "video"],
    "max_input_size_mb": 10,
    "supported_formats": {
      "image": ["jpeg", "jpg", "png", "webp", "gif"],
      "audio": ["mp3", "wav", "ogg", "m4a"],
      "video": ["mp4", "webm", "mov"],
      "document": ["pdf", "txt", "md", "json", "csv", "docx"]
    }
  },
  "authentication": {
    "type": "jwt",
    "required": true
  }
}
```

---

## POST /run

Endpoint de produção. Executa o agente e retorna resultado final.

### Request

```json
{
  "input": [
    {
      "type": "text",
      "content": "Qual a capital do Brasil?"
    }
  ],
  "conversation_id": "conv_abc123",
  "model": "claude-sonnet-4-20250514",
  "config": {
    "temperature": 0.7,
    "max_tokens": 1000
  }
}
```

### Campos do Input

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `input` | array | Sim | Lista de items de input |
| `input[].type` | string | Sim | Tipo: text, image, audio, document, video |
| `input[].content` | string | Sim | Conteúdo (texto ou base64) |
| `input[].filename` | string | Não | Nome do arquivo |
| `input[].mime_type` | string | Não | MIME type (ex: image/png) |
| `conversation_id` | string | Sim | ID único da conversa |
| `model` | string | Não | Override do modelo padrão |
| `config` | object | Não | Configurações de geração |

### Response

```json
{
  "conversation_id": "conv_abc123",
  "final_output": {
    "message": "A capital do Brasil é Brasília.",
    "state": {
      "context_used": true,
      "tools_called": 0
    },
    "actions_taken": []
  },
  "metrics": {
    "latency_ms": 1234,
    "tokens_used": 150,
    "input_tokens": 50,
    "output_tokens": 100,
    "cost_estimate": 0.0015
  }
}
```

---

## POST /run_debug

Igual ao `/run`, mas inclui `trajectory` com observabilidade completa.

```json
{
  "conversation_id": "conv_abc123",
  "final_output": { "..." },
  "metrics": { "..." },
  "trajectory": [
    {
      "stage_id": "main",
      "stage_type": "agent",
      "timestamp": "2024-01-15T10:30:00.000Z",
      "input": {
        "messages": [{"role": "user", "content": "..."}]
      },
      "output": {
        "message": "Resposta...",
        "tool_calls": []
      },
      "metrics": {
        "latency_ms": 1234,
        "tokens_used": 150
      },
      "model_used": "claude-sonnet-4-20250514"
    }
  ]
}
```

---

## Input Multimodal

```json
{
  "input": [
    {
      "type": "text",
      "content": "Descreva esta imagem"
    },
    {
      "type": "image",
      "content": "base64_encoded_image_data...",
      "mime_type": "image/jpeg"
    }
  ],
  "conversation_id": "conv_multimodal_001"
}
```

---

## Conversação Multi-turn

O `conversation_id` mantém contexto entre requisições:

```python
# Primeira mensagem
POST /run
{
  "input": [{"type": "text", "content": "Meu nome é João"}],
  "conversation_id": "conv_001"
}

# Segunda mensagem - mesmo conversation_id
POST /run
{
  "input": [{"type": "text", "content": "Qual é meu nome?"}],
  "conversation_id": "conv_001"
}
# Resposta: "Seu nome é João"
```

---

## Erros Padronizados

| Status | Descrição | Quando Usar |
|--------|-----------|-------------|
| 200 | Sucesso | Execução normal |
| 400 | Bad Request | Input inválido |
| 401 | Unauthorized | Token JWT inválido |
| 422 | Validation Error | Schema inválido |
| 429 | Rate Limited | Muitas requisições |
| 500 | Internal Error | Erro no módulo |
| 503 | Unavailable | Módulo indisponível |

---

## Referência Completa

Para a especificação completa, veja [PADRAO_AGENT_BENCH.md](../PADRAO_AGENT_BENCH.md).
