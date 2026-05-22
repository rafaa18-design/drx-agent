"""Tools de sessão: salvar dados do cliente, preferências e ver contexto."""

import logging
from datetime import datetime

import httpx

from app.runtime import RunContext, tool
from app.tools._helpers import ensure_state

logger = logging.getLogger(__name__)
_API = "http://localhost:8000"


@tool
async def salvar_dados_cliente(
    run_context: RunContext,
    nome: str = "",
    telefone: str = "",
    email: str = "",
) -> str:
    """Salva nome, telefone e e-mail do lead na sessão e atualiza o CRM.

    Use sempre que o lead informar dados pessoais durante a conversa.
    Campos vazios não sobrescrevem dados já salvos.

    Args:
        nome: Nome completo do lead.
        telefone: Número com DDD (ex: 11999990001).
        email: E-mail do lead (opcional).

    Returns:
        Confirmação dos dados salvos.
    """
    state = ensure_state(run_context)

    # Atualiza session_state
    if nome:
        state["client_name"] = nome
    if telefone:
        state["phone"] = telefone
    elif not state.get("phone") and run_context.session_id:
        # Usa session_id como telefone se ainda não tiver número registrado
        import re
        if len(re.sub(r"\D", "", run_context.session_id)) >= 8:
            state["phone"] = run_context.session_id
    if email:
        state["client_email"] = email

    # Persiste no CRM se já tiver o lead criado
    db_lead_id = state.get("db_lead_id")
    if db_lead_id:
        patch: dict = {}
        if nome:
            patch["name"] = nome
        if telefone:
            patch["phone"] = telefone
        if email:
            patch["email"] = email
        if patch:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.patch(f"{_API}/api/leads/{db_lead_id}", json=patch)
            except Exception as e:
                logger.warning("Falha ao atualizar dados no CRM: %s", e)

    salvos = []
    if nome:     salvos.append(f"nome: {nome}")
    if telefone: salvos.append(f"telefone: {telefone}")
    if email:    salvos.append(f"email: {email}")

    return "Dados salvos: " + ", ".join(salvos) if salvos else "Nenhum dado novo informado."


@tool
def salvar_preferencias(
    run_context: RunContext,
    chave: str,
    valor: str,
) -> str:
    """Salva uma preferência ou anotação temporária do paciente para esta sessão.

    Use esta ferramenta para guardar qualquer informação relevante que o paciente
    mencione e que pode ser útil durante o atendimento, como:
    - Horários preferidos (ex: "prefere manhã", "só pode terça e quinta")
    - Dentista preferido (ex: "prefere Dra. Maria")
    - Alergias ou observações (ex: "alergia a látex", "ansioso com agulhas")
    - Procedimentos de interesse (ex: "interessado em clareamento")
    - Qualquer outra nota relevante

    Args:
        chave: Nome da preferência (ex: "horario_preferido", "dentista_preferido", "alergias").
        valor: Valor da preferência (ex: "manhã, terça ou quinta", "Dra. Maria Silva").

    Returns:
        Confirmação da preferência salva.
    """
    state = ensure_state(run_context)

    if "preferencias" not in state:
        state["preferencias"] = {}

    state["preferencias"][chave] = {
        "valor": valor,
        "salvo_em": datetime.now().isoformat(),
    }

    return f"Preferência salva: {chave} = {valor}"


@tool
def ver_contexto_sessao(run_context: RunContext) -> str:
    """Recupera todos os dados do cliente e preferências salvos nesta sessão.

    Use esta ferramenta no início de um atendimento ou quando precisar relembrar
    informações do paciente que foram coletadas anteriormente na conversa.
    Isso é especialmente útil em conversas longas.

    Returns:
        Resumo de todos os dados e preferências salvos na sessão.
    """
    state = ensure_state(run_context)

    linhas = []

    # Dados do cliente
    cliente = state.get("cliente", {})
    if cliente:
        linhas.append("📋 Dados do cliente:")
        for k, v in cliente.items():
            if k != "atualizado_em" and v:
                linhas.append(f"  • {k}: {v}")
    else:
        linhas.append("📋 Nenhum dado do cliente salvo ainda.")

    # Preferências
    prefs = state.get("preferencias", {})
    if prefs:
        linhas.append("\n⭐ Preferências:")
        for k, info in prefs.items():
            linhas.append(f"  • {k}: {info['valor']}")
    else:
        linhas.append("\n⭐ Nenhuma preferência registrada.")

    # Agendamentos
    agendamentos = state.get("agendamentos", [])
    ativos = [a for a in agendamentos if a.get("status") != "cancelado"]
    if ativos:
        linhas.append(f"\n📅 Agendamentos ativos ({len(ativos)}):")
        for a in ativos:
            linhas.append(
                f"  • {a['id']}: {a['servico_nome']} em {a['data']} às {a['horario']} "
                f"com {a['dentista_nome']}"
            )

    return "\n".join(linhas) if linhas else "Sessão vazia — nenhum dado salvo ainda."
