"""Tools de análise visual de prints para DRX Advogados.

Usa Gemini 2.5 Flash para extração estruturada das imagens enviadas pelo lead.
Salva platform/case_type no session_state e atualiza o CRM automaticamente.
"""

import json
import logging

import httpx

from app.config import settings
from app.runtime import RetryAgentRun, RunContext, tool

_API = "http://localhost:8000"

logger = logging.getLogger(__name__)

_VISION_MODEL = "gemini/gemini-2.5-flash"

_PROMPT_PERFIL = """
Analise este print de perfil de rede social e retorne SOMENTE um JSON válido, sem texto adicional.

{
  "platform": "instagram|tiktok|youtube|twitter|outro",
  "username": "nome de usuário ou null",
  "followers": número inteiro estimado (leia do print) ou null,
  "verified": true ou false,
  "bio": "texto da bio ou null",
  "niche": "categoria do conteúdo (ex: marketing digital, fitness, culinária, conteúdo adulto, etc)",
  "professional_indicators": ["lista de sinais profissionais visíveis na bio ou perfil"],
  "monetization_signals": ["lista de sinais de monetização visíveis (link na bio, loja, produto, etc)"],
  "signals": ["lista de sinais para score — use APENAS os valores abaixo"],
  "confidence": "alta|media|baixa"
}

Sinais permitidos para o campo signals:
- followers_300k_plus      (300k ou mais seguidores)
- followers_100k_to_300k   (100k a 299k)
- followers_10k_to_100k    (10k a 99k)
- followers_5k_to_10k      (5k a 9k)
- followers_below_5k       (menos de 5k)
- verified_badge           (selo verificado visível)
- professional_bio_with_link (bio tem link de produto/serviço)
- high_ticket_profession   (médico, advogado, nutricionista, empresário)
- digital_marketing        (marketing digital, criador de conteúdo)
- adult_content_monetized  (conteúdo adulto com monetização)
- monetization_history     (sinais de monetização histórica)
- blank_or_personal_bio    (bio em branco ou uso pessoal)
- no_monetization_signal   (nenhum sinal de monetização)

Inclua APENAS os sinais que você consegue confirmar visualmente no print.
Retorne SOMENTE o JSON, sem markdown, sem explicação.
"""

_PROMPT_PROBLEMA = """
Analise este print de problema em rede social e retorne SOMENTE um JSON válido, sem texto adicional.

{
  "platform": "instagram|tiktok|youtube|twitter|outro",
  "account_affected": "username afetado se visível ou null",
  "issue_type": "banimento|restricao|bloqueio|aviso|suspensao|outro",
  "severity": "permanente|temporario|aviso",
  "description": "resumo do problema em 1 frase curta",
  "signals": ["lista de sinais para score — use APENAS os valores abaixo"],
  "confidence": "alta|media|baixa"
}

Sinais permitidos para o campo signals:
- permanent_ban        (banimento permanente)
- temporary_restriction (restrição temporária)
- warning_only         (apenas aviso, sem restrição ativa)

Retorne SOMENTE o JSON, sem markdown, sem explicação.
"""


async def _resolve_lead_id(run_context: RunContext) -> str | None:
    """Retorna o db_lead_id da sessão ou busca pelo telefone como fallback."""
    lead_id = run_context.session_state.get("db_lead_id")
    if lead_id:
        return lead_id

    phone = run_context.session_state.get("phone") or run_context.session_id
    if not phone:
        return None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{_API}/api/leads", params={"search": phone})
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    found_id = items[0]["id"]
                    run_context.session_state["db_lead_id"] = found_id
                    return found_id
    except Exception as e:
        logger.warning("Falha ao buscar lead por telefone: %s", e)

    return None


async def _patch_lead(run_context: RunContext, data: dict) -> None:
    """Atualiza campos do lead no CRM, resolvendo o ID automaticamente."""
    lead_id = await _resolve_lead_id(run_context)
    if not lead_id:
        logger.warning("_patch_lead: nenhum lead_id encontrado na sessão")
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.patch(f"{_API}/api/leads/{lead_id}", json=data)
    except Exception as e:
        logger.warning("Falha ao atualizar lead no CRM: %s", e)


async def _call_vision_bytes(image_bytes: bytes, mime_type: str, prompt: str) -> dict:
    """Chama Gemini Flash com bytes da imagem via google.generativeai SDK e retorna JSON."""
    import google.generativeai as genai
    from app.config import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(_VISION_MODEL.replace("gemini/", ""))

    # Formato dict — compatível com todas as versões do SDK
    image_part = {"mime_type": mime_type, "data": image_bytes}

    response = model.generate_content([prompt, image_part])
    raw = (response.text or "").strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]

    return json.loads(raw)


@tool
async def analyze_profile_print(run_context: RunContext) -> str:
    """Analisa o print do perfil público do lead e extrai sinais de qualificação.

    Use assim que o lead enviar o print do perfil (ponto 02 da coleta).
    A imagem é lida automaticamente — não precisa de parâmetros extras.
    Retorna os sinais prontos para passar ao qualify_lead().

    Returns:
        JSON com plataforma, seguidores, nicho e sinais de score.
    """
    from app.tools.drx.image_store import get_latest_image

    entry = get_latest_image(run_context.session_id)
    if not entry:
        raise RetryAgentRun(
            "Não encontrei a imagem na sessão. Peça ao lead para enviar o print do perfil."
        )

    try:
        result = await _call_vision_bytes(entry.data, entry.mime_type, _PROMPT_PERFIL)
    except json.JSONDecodeError as e:
        raise RetryAgentRun(
            "Não consegui ler o print do perfil com clareza. "
            "Peça ao lead para enviar uma imagem mais nítida."
        ) from e
    except Exception as e:
        logger.error("analyze_profile_print falhou: %s", e)
        raise RetryAgentRun(
            "Erro ao analisar o print do perfil. Tente novamente."
        ) from e

    followers  = result.get("followers")
    niche      = result.get("niche") or "não identificado"
    signals    = result.get("signals", [])
    confidence = result.get("confidence", "media")
    platform   = result.get("platform") or "desconhecida"

    # Salva no session_state
    run_context.session_state["platform"]  = platform
    run_context.session_state["followers"] = followers

    # Atualiza lead no CRM (resolve ID por sessão ou busca por telefone)
    await _patch_lead(run_context, {"platform": platform})

    summary_lines = [
        f"Plataforma: {platform}",
        f"Seguidores: {followers:,}".replace(",", ".") if followers else "Seguidores: não identificado",
        f"Nicho: {niche}",
        f"Verificado: {'sim' if result.get('verified') else 'não'}",
        f"Sinais de score: {', '.join(signals) if signals else 'nenhum'}",
        f"Confiança da análise: {confidence}",
    ]

    return "\n".join(summary_lines) + f"\n\n_signals_json: {json.dumps(signals)}"


@tool
async def analyze_problem_print(run_context: RunContext) -> str:
    """Analisa o print do problema da conta e identifica tipo e severidade.

    Use assim que o lead enviar o print do problema (ponto 01 da coleta).
    A imagem é lida automaticamente — não precisa de parâmetros extras.
    Retorna o tipo de problema e sinais de score.

    Returns:
        Tipo de problema, severidade e sinais de score.
    """
    from app.tools.drx.image_store import get_latest_image

    entry = get_latest_image(run_context.session_id)
    if not entry:
        raise RetryAgentRun(
            "Não encontrei a imagem na sessão. Peça ao lead para enviar o print do problema."
        )

    try:
        result = await _call_vision_bytes(entry.data, entry.mime_type, _PROMPT_PROBLEMA)
    except json.JSONDecodeError as e:
        raise RetryAgentRun(
            "Não consegui ler o print do problema com clareza. "
            "Peça ao lead para enviar uma imagem mais nítida."
        ) from e
    except Exception as e:
        logger.error("analyze_problem_print falhou: %s", e)
        raise RetryAgentRun(
            "Erro ao analisar o print do problema. Tente novamente."
        ) from e

    signals   = result.get("signals", [])
    platform  = result.get("platform") or "desconhecida"
    issue     = result.get("issue_type") or "desconhecido"
    desc      = result.get("description") or ""

    # Salva no session_state para qualify_lead e exibição no CRM
    run_context.session_state["platform"]         = platform
    run_context.session_state["issue_type"]       = issue
    run_context.session_state["problem_description"] = desc

    # Atualiza lead no CRM (resolve ID por sessão ou busca por telefone)
    await _patch_lead(run_context, {
        "platform":         platform,
        "case_type":        issue,
        "case_description": desc,
    })

    summary_lines = [
        f"Plataforma: {platform}",
        f"Problema: {issue}",
        f"Severidade: {result.get('severity', 'desconhecida')}",
        f"Descrição: {desc or 'não identificada'}",
        f"Sinais de score: {', '.join(signals) if signals else 'nenhum'}",
        f"Confiança da análise: {result.get('confidence', 'media')}",
    ]

    return "\n".join(summary_lines) + f"\n\n_signals_json: {json.dumps(signals)}"
