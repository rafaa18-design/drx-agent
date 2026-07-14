"""Tools de gestão de leads DRX — com persistência no banco via API."""

import logging

import httpx

from app.runtime import RetryAgentRun, RunContext, tool
from app.tools.drx.qualification import calculate_score

logger = logging.getLogger(__name__)

VALID_STATUSES = {"new", "contacted", "qualified", "proposal", "won", "follow_up", "lost"}
_API = "http://localhost:8000"


async def _get_or_create_lead(phone: str, session: dict) -> dict | None:
    """Busca lead pelo telefone no banco. Cria se não existir."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Busca pelo telefone
            r = await client.get(f"{_API}/api/leads", params={"search": phone})
            if r.status_code == 200:
                data = r.json()
                if data["items"]:
                    return data["items"][0]

            # Cria novo lead
            payload = {
                "phone": phone,
                "name": session.get("client_name"),
                "source": session.get("lead_source", "unknown"),
                "platform": session.get("platform"),
                "case_type": session.get("issue_type"),
                "case_description": session.get("problem_description"),
                "commercial_status": "contacted",
            }
            r = await client.post(f"{_API}/api/leads", json=payload)
            if r.status_code == 201:
                return r.json()
            if r.status_code == 409:
                # Já existe — busca novamente
                r2 = await client.get(f"{_API}/api/leads", params={"search": phone})
                if r2.status_code == 200 and r2.json()["items"]:
                    return r2.json()["items"][0]
    except Exception as e:
        logger.warning("Erro ao acessar API CRM: %s", e)
    return None


@tool
async def qualify_lead(
    run_context: RunContext,
    lead_id: str,
    signals: list[str],
    notes: str = "",
) -> str:
    """Qualifica um lead DRX com base nos sinais coletados nos 6 pontos de dados.

    Chame esta tool após coletar os 6 dados do lead (prints + texto).
    Se auto_meeting=True na resposta, agende reunião imediatamente sem mais perguntas.

    Sinais disponíveis — alcance:
      followers_300k_plus, followers_100k_to_300k, followers_10k_to_100k,
      followers_5k_to_10k, followers_below_5k

    Sinais disponíveis — profissionalismo e monetização:
      professional_monetizer, high_ticket_profession, digital_marketing,
      adult_content_monetized, professional_bio_with_link, verified_badge,
      monetization_history, professional_use, hobby_use

    Sinais disponíveis — prejuízo financeiro:
      monthly_loss_above_5k, monthly_loss_1k_to_5k, monthly_loss_below_1k,
      no_financial_loss

    Sinais disponíveis — qualidade do perfil:
      blank_or_personal_bio, no_monetization_signal

    Sinais disponíveis — gravidade do problema:
      permanent_ban, temporary_restriction, warning_only

    Sinais disponíveis — origem:
      referral_lead, existing_client

    Args:
        lead_id: Telefone ou ID do lead.
        signals: Lista de sinais identificados na conversa.
        notes: Observações adicionais sobre o caso.

    Returns:
        Score, nível, auto_meeting e ação recomendada.
    """
    # Sinais vazios geram score 0 / desqualificado indevido — força o modelo a mapear
    if not signals:
        raise RetryAgentRun(
            "A lista de signals está vazia. Mapeie o que o lead disse para os sinais da docstring "
            "(ex: '90 mil seguidores' → followers_10k_to_100k; 'fonte de renda' → professional_use; "
            "'marketing digital' → digital_marketing; restrição no print → temporary_restriction) "
            "e chame qualify_lead novamente com eles."
        )

    LOW_FOLLOWER_SIGNALS = {"followers_below_5k", "followers_5k_to_10k"}
    HOBBY_SIGNALS = {"hobby_use"}
    has_low_followers = bool(LOW_FOLLOWER_SIGNALS.intersection(signals))
    is_hobby = bool(HOBBY_SIGNALS.intersection(signals))

    result = calculate_score(signals)

    run_context.session_state["qualification"] = {
        "lead_id": lead_id,
        "score": result.score,
        "level": result.level,
        "auto_meeting": result.auto_meeting,
        "signals": signals,
        "notes": notes,
    }

    # Persistir no banco via API
    phone = run_context.session_state.get("phone") or lead_id
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Busca lead existente
            r = await client.get(f"{_API}/api/leads", params={"search": phone})
            existing = r.json()["items"][0] if r.status_code == 200 and r.json()["items"] else None

            platform    = run_context.session_state.get("platform")
            issue_type  = run_context.session_state.get("issue_type")
            description = notes or run_context.session_state.get("problem_description")

            patch_data = {
                "qualification_score": result.score,
                "qualification_level": result.level,
                "qualification_signals": {"signals": signals, "events": result.events},
                "commercial_status": "qualified" if not result.auto_meeting else "proposal",
                **({"platform": platform}   if platform   else {}),
                **({"case_type": issue_type} if issue_type else {}),
                **({"case_description": description} if description else {}),
            }

            if existing:
                await client.patch(f"{_API}/api/leads/{existing['id']}", json=patch_data)
                run_context.session_state["db_lead_id"] = existing["id"]
            else:
                # Cria o lead se não existir
                create_data = {
                    "phone": phone,
                    "name": run_context.session_state.get("client_name"),
                    "source": run_context.session_state.get("lead_source", "unknown"),
                    "platform": platform,
                    "case_type": issue_type,
                    "case_description": description,
                    **patch_data,
                }
                r2 = await client.post(f"{_API}/api/leads", json=create_data)
                if r2.status_code == 201:
                    run_context.session_state["db_lead_id"] = r2.json()["id"]
    except Exception as e:
        logger.warning("Falha ao persistir qualificação no CRM: %s", e)

    lines = [
        f"Score: {result.score}/100",
        f"Nível: {result.level.upper()}",
        f"Reunião automática: {'SIM — agendar agora' if result.auto_meeting else 'não'}",
        f"Ação recomendada: {result.recommended_action}",
    ]
    if result.events:
        lines.append("Sinais computados: " + ", ".join(e["signal"] for e in result.events))

    if has_low_followers:
        lines.append(
            "BLOQUEIO DE REUNIÃO: lead tem menos de 10 mil seguidores. "
            "NÃO ofereça nem agende reunião. "
            "Siga a regra de lead com poucos seguidores do prompt."
        )
        run_context.session_state["meeting_blocked"] = True

    if is_hobby and not has_low_followers:
        lines.append(
            "BLOQUEIO DE REUNIÃO: conta é pessoal/hobby, não profissional. "
            "NÃO ofereça nem agende reunião. "
            "Siga a regra de lead com conta pessoal do prompt."
        )
        run_context.session_state["meeting_blocked"] = True

    return "\n".join(lines)


def _is_valid_phone(value: str) -> bool:
    """Retorna True se o valor contém pelo menos 8 dígitos (parece um telefone real)."""
    import re
    return len(re.sub(r"\D", "", value)) >= 8


@tool
async def get_lead_context(run_context: RunContext) -> str:
    """Recupera o contexto completo do lead desta conversa no CRM.

    Use na PRIMEIRA mensagem para verificar se é cliente da casa. O telefone
    é identificado automaticamente pelo canal — não pergunte nem invente
    um número, esta tool não recebe telefone como parâmetro.

    Returns:
        Dados do lead, histórico resumido e status no CRM.
    """
    # O telefone real é o identificador da conversa (conversation_id/session_id)
    # — NUNCA pedimos isso ao modelo, porque ele não tem como saber o número
    # de verdade e acaba inventando um (bug real observado em produção: o
    # modelo "chutou" um telefone válido-mas-falso, criando um lead fantasma
    # desconectado da conversa real).
    phone = run_context.session_id or ""
    if not _is_valid_phone(phone):
        return "Nenhum telefone válido identificado. Continue o atendimento normalmente."

    # Salva o telefone na sessão para uso posterior
    run_context.session_state["phone"] = phone

    # Verifica cache local
    cached = run_context.session_state.get("lead_context")
    if cached and cached.get("phone") == phone:
        return f"Lead encontrado (cache): {cached}"

    # Busca no banco
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{_API}/api/leads", params={"search": phone})
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    lead = items[0]
                    run_context.session_state["db_lead_id"] = lead["id"]
                    run_context.session_state["lead_context"] = {"phone": phone, **lead}
                    return (
                        f"Cliente encontrado no CRM.\n"
                        f"Nome: {lead.get('name') or 'não informado'}\n"
                        f"Status: {lead.get('commercial_status', 'new')}\n"
                        f"Score: {lead.get('qualification_score', 0)}\n"
                        f"Plataforma: {lead.get('platform') or 'não informada'}\n"
                        f"IA ativa: {'sim' if lead.get('ai_active', True) else 'não'}"
                    )
    except Exception as e:
        logger.warning("Erro ao buscar lead no CRM: %s", e)

    # Registra como novo contato
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{_API}/api/leads", json={
                "phone": phone,
                "source": run_context.session_state.get("lead_source", "unknown"),
                "commercial_status": "new",
            })
            if r.status_code == 201:
                run_context.session_state["db_lead_id"] = r.json()["id"]
    except Exception as e:
        logger.warning("Erro ao criar lead no CRM: %s", e)

    return f"Nenhum histórico encontrado para {phone}. Novo contato registrado."


@tool
async def update_lead_status(
    run_context: RunContext,
    lead_id: str,
    status: str,
    notes: str = "",
) -> str:
    """Atualiza o status comercial do lead no CRM.

    Args:
        lead_id: ID ou telefone do lead.
        status: Novo status (new, contacted, qualified, proposal, won, lost).
        notes: Observação sobre a atualização.

    Returns:
        Confirmação da atualização.
    """
    if status not in VALID_STATUSES:
        raise RetryAgentRun(
            f'Status "{status}" inválido. '
            f"Use um de: {', '.join(sorted(VALID_STATUSES))}"
        )

    run_context.session_state["lead_status"] = {"lead_id": lead_id, "status": status}

    # Pega o ID do banco salvo na sessão, ou usa o lead_id direto
    db_id = run_context.session_state.get("db_lead_id") or lead_id

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.patch(
                f"{_API}/api/leads/{db_id}",
                json={"commercial_status": status},
            )
            if r.status_code == 200:
                return f"Status do lead atualizado para '{status}' no CRM."
            if r.status_code == 404:
                # Tenta buscar pelo telefone
                phone = run_context.session_state.get("phone", lead_id)
                r2 = await client.get(f"{_API}/api/leads", params={"search": phone})
                if r2.status_code == 200 and r2.json()["items"]:
                    found_id = r2.json()["items"][0]["id"]
                    await client.patch(f"{_API}/api/leads/{found_id}", json={"commercial_status": status})
                    run_context.session_state["db_lead_id"] = found_id
                    return f"Status do lead atualizado para '{status}' no CRM."
    except Exception as e:
        logger.warning("Erro ao atualizar status no CRM: %s", e)

    return f"Status '{status}' salvo localmente (CRM indisponível)."
