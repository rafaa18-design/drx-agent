# Skills (Habilidades)

Agno Skills, baseado na especificação [Agent Skills da Anthropic](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview), é uma forma de estender as capacidades do agente fornecendo habilidades específicas.

---

## O que é uma Skill?

Uma skill é um pacote auto-contido que um agente pode usar para estender suas capacidades em um domínio específico ou adquirir uma nova capacidade.

### Componentes de uma Skill

| Componente | Descrição |
|------------|-----------|
| **Instructions** | Orientações detalhadas em `SKILL.md` |
| **Scripts** | Templates de código executável (opcional) |
| **References** | Documentação de suporte (guias, exemplos) |

---

## Estrutura do SKILL.md

```markdown
---
name: code-review
description: Code review assistance with style checking and best practices
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: your-name
  tags: ["python", "code-quality"]
---

# Code Review Skill

Use this skill when reviewing code for quality, style, and best practices.

## When to Use

- User asks for code review or feedback
- User wants to improve code quality
- User needs help with refactoring

## Process

1. **Analyze Structure**: Review overall code organization
2. **Check Style**: Look for style guide violations
3. **Identify Issues**: Find bugs, security issues, performance problems
4. **Suggest Improvements**: Provide actionable recommendations

## Best Practices

- Focus on the most impactful issues first
- Explain the "why" behind suggestions
- Provide code examples for fixes
```

---

## Scripts Executáveis

Scripts são templates de código que o agente pode executar.

### Exemplo: Verificador de Estilo Python

```python
#!/usr/bin/env python3
"""Check code style and return results."""

import sys

def check_style(code: str) -> dict:
    issues = []
    lines = code.split('\n')

    for i, line in enumerate(lines, 1):
        if len(line) > 100:
            issues.append(f"Line {i}: exceeds 100 characters")
        if line.endswith(' '):
            issues.append(f"Line {i}: trailing whitespace")

    return {"issues": issues, "count": len(issues)}

if __name__ == "__main__":
    # Read code from stdin or argument
    code = sys.stdin.read() if not sys.argv[1:] else sys.argv[1]
    result = check_style(code)
    print(result)
```

---

## Carregando Skills

### LocalSkills (Diretório Local)

```python
from pathlib import Path
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.skills import Skills, LocalSkills

# Diretório de skills relativo ao arquivo
skills_dir = Path(__file__).parent / "skills"

# Criar agente com skills
agent = Agent(
    name="Code Assistant",
    model=OpenAIChat(id="gpt-4o"),
    skills=Skills(loaders=[LocalSkills(str(skills_dir))]),
    instructions=[
        "You are a helpful coding assistant with access to specialized skills."
    ],
    markdown=True,
)

if __name__ == "__main__":
    agent.print_response(
        "Review this Python function:\n\n"
        "def calc(x,y): return x+y"
    )
```

### Com Instruções Customizadas

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.skills import Skills, LocalSkills

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    skills=Skills(loaders=[LocalSkills("/path/to/skills")]),
    instructions=[
        "You have access to specialized skills.",
        "Use get_skill_instructions to load full guidance when needed.",
    ],
)

# O agente usará skills automaticamente quando relevante
agent.print_response("Review this code for best practices: def foo(): pass")
```

---

## Skills Anthropic (Claude)

Claude suporta skills nativas para geração de documentos.

### Skills de Documentos

```python
from agno.agent import Agent
from agno.models.anthropic import Claude

# Agente com múltiplas skills de documentos
agent = Agent(
    name="Document Generator",
    model=Claude(
        id="claude-sonnet-4-20250514",
        skills=[
            {"type": "anthropic", "skill_id": "pptx", "version": "1.0"},
            {"type": "anthropic", "skill_id": "xlsx", "version": "1.0"},
            {"type": "anthropic", "skill_id": "docx", "version": "1.0"},
            {"type": "anthropic", "skill_id": "pdf", "version": "1.0"},
        ],
    ),
    instructions=[
        "You can generate professional documents.",
        "Create presentations, spreadsheets, and documents as needed.",
    ],
    markdown=True,
)
```

### Skills Disponíveis

| Skill ID | Descrição |
|----------|-----------|
| `pptx` | Apresentações PowerPoint |
| `xlsx` | Planilhas Excel |
| `docx` | Documentos Word |
| `pdf` | Documentos PDF |

---

## Por que usar Skills?

### Pacotes Reutilizáveis

Crie skills uma vez, use em múltiplos agentes:

```python
# Uma skill de code review pode ser compartilhada entre:
# - Agente de debugging
# - Agente de PR review
# - Agente de geração de código

code_review_skill = LocalSkills("/skills/code-review")

debugging_agent = Agent(
    name="Debugger",
    skills=Skills(loaders=[code_review_skill]),
)

pr_review_agent = Agent(
    name="PR Reviewer",
    skills=Skills(loaders=[code_review_skill]),
)
```

### Descoberta Gradual

Agentes podem **descobrir, obter e utilizar** conhecimento especializado gradualmente:

```python
agent = Agent(
    skills=Skills(loaders=[LocalSkills("/skills")]),
    instructions=[
        "You have access to specialized skills.",
        "Discover and use relevant skills as needed.",
    ],
)
```

---

## Estrutura de Diretório de Skills

```
skills/
├── code-review/
│   ├── SKILL.md           # Instruções principais
│   ├── scripts/
│   │   └── check_style.py # Scripts executáveis
│   └── references/
│       └── style_guide.md # Documentação de suporte
├── data-analysis/
│   ├── SKILL.md
│   └── scripts/
│       └── analyze.py
└── documentation/
    └── SKILL.md
```

---

## Referências

- [Agno Skills](https://docs.agno.com/basics/skills/overview)
- [Anthropic Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
