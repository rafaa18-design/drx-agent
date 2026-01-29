# Dependencies (Injeção de Dependências)

O Agno suporta injeção de dependências para fornecer contexto e recursos às tools.

---

## Conceito

Dependencies permitem injetar dados e serviços que tools podem acessar em runtime através do `RunContext`.

---

## Dependências Estáticas

```python
from agno.agent import Agent


class APIClient:
    def fetch(self, endpoint: str) -> dict:
        return {"data": f"Resultado de {endpoint}"}


api_client = APIClient()

agent = Agent(
    dependencies={
        "api_client": api_client,
        "config": {"max_results": 10},
    },
)


def buscar_dados(run_context: RunContext, endpoint: str) -> str:
    """Busca dados da API."""
    client = run_context.dependencies["api_client"]
    config = run_context.dependencies["config"]

    result = client.fetch(endpoint)
    return f"Dados: {result} (max: {config['max_results']})"
```

---

## Dependências Dinâmicas

```python
from agno.agent import Agent
from agno.run import RunContext


def get_user_profile(run_context: RunContext) -> str:
    """Obtém perfil do usuário via dependencies."""
    profiles = run_context.dependencies.get("user_profiles", {})
    user_id = run_context.user_id
    return profiles.get(user_id, "Perfil não encontrado")


# Injetar profiles dinamicamente
user_profiles = {
    "user_123": {"name": "João", "tier": "premium"},
    "user_456": {"name": "Maria", "tier": "basic"},
}

agent = Agent(
    dependencies={"user_profiles": user_profiles},
    tools=[get_user_profile],
)

response = agent.run("Qual meu perfil?", user_id="user_123")
```

---

## Dependências Callable

```python
from datetime import datetime


def get_current_context() -> dict:
    """Função executada em runtime."""
    return {
        "current_time": datetime.now().isoformat(),
        "timezone": "America/Sao_Paulo",
        "day_of_week": datetime.now().strftime("%A"),
    }


agent = Agent(
    dependencies={
        # Callable - executado em runtime
        "current_context": get_current_context,
    },
)
```

---

## Acessando Dependencies em Tools

```python
from agno.run import RunContext


def buscar_perfil(run_context: RunContext) -> str:
    """Tool que acessa dependencies."""
    profiles = run_context.dependencies["user_profiles"]
    user_id = run_context.user_id

    perfil = profiles.get(user_id)
    if not perfil:
        return "Perfil não encontrado"

    return f"Usuário: {perfil['name']}, Plano: {perfil['tier']}"


def obter_config(run_context: RunContext, key: str) -> str:
    """Tool que acessa configuração."""
    config = run_context.dependencies.get("config", {})
    return str(config.get(key, "Não configurado"))
```

---

## Injetando Dependencies no Contexto

```python
# Adiciona dependencies automaticamente ao prompt do usuário
agent = Agent(
    dependencies={
        "user_name": "João",
        "preferences": {"idioma": "pt-BR"},
    },
    # Injeta dependencies no contexto do modelo
    add_dependencies_to_context=True,
)

# O modelo recebe as dependencies junto com a mensagem
agent.print_response("Qual meu nome e idioma preferido?")
```

---

## Dependencies no Runtime

```python
# Passar dependencies na execução
response = agent.run(
    "Analise o contexto atual",
    dependencies={
        "runtime_data": {"timestamp": "2024-01-15T10:30:00"},
    },
    add_dependencies_to_context=True,
)
```

---

## Padrão de Serviços

```python
class DatabaseService:
    def query(self, sql: str) -> list:
        # Implementação
        pass


class CacheService:
    def get(self, key: str) -> any:
        pass

    def set(self, key: str, value: any, ttl: int = 3600):
        pass


def create_agent_with_services() -> Agent:
    return Agent(
        tools=[query_data, cache_result],
        dependencies={
            "db": DatabaseService(),
            "cache": CacheService(),
        },
    )


# Na tool
def query_data(run_context: RunContext, query: str) -> str:
    db = run_context.dependencies["db"]
    cache = run_context.dependencies["cache"]

    # Verifica cache
    cached = cache.get(f"query:{query}")
    if cached:
        return cached

    # Executa query
    result = db.query(query)
    cache.set(f"query:{query}", result)
    return str(result)
```

---

## Referências

- [Agno Dependencies](https://docs.agno.com/basics/dependencies)
