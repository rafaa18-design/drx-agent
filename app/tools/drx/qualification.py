"""Scoring engine para qualificação de leads DRX Advogados.

Contexto: leads que perderam acesso a contas em redes sociais (Instagram, TikTok, YouTube).
A DRX atua na recuperação jurídica dessas contas.

Lógica principal:
  1. Sinais de reunião automática (bypass total do score) — verificar primeiro.
  2. Matriz de score — soma ponderada de sinais coletados nos 6 pontos.
  3. Nível de qualificação — determina a ação recomendada.
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Sinais que disparam reunião automática independente do score
# Baseado nas regras: Nó 01 (300k+) e Nó 02 (profissional que monetiza)
# ---------------------------------------------------------------------------
AUTO_MEETING_SIGNALS = {
    "followers_300k_plus",       # 300 mil seguidores ou mais — pula a fila
    "professional_monetizer",    # médico, advogado, nutricionista, empresário,
                                 # marketing digital, conteúdo adulto monetizado
}

# ---------------------------------------------------------------------------
# Matriz de score — sinais dos 6 pontos de coleta
# ---------------------------------------------------------------------------
SCORING_MATRIX = {
    # --- Alcance (Ponto 02 e 04) ---
    "followers_300k_plus":        40,   # Nó 01 — reunião automática, mas score alto também
    "followers_100k_to_300k":     25,
    "followers_10k_to_100k":      10,
    "followers_5k_to_10k":       -50,   # < 10k — não agenda reunião
    "followers_below_5k":        -50,   # < 10k — não agenda reunião

    # --- Profissionalismo e monetização (Ponto 02, 05) ---
    "professional_bio_with_link": 15,   # bio tem link de produto/serviço
    "verified_badge":             15,   # selo verificado na plataforma
    "high_ticket_profession":     20,   # médico, advogado, nutricionista, empresário
    "digital_marketing":          20,   # marketing digital / criador de conteúdo
    "adult_content_monetized":    25,   # conteúdo adulto com monetização
    "monetization_history":       15,   # histórico comprovado de monetização
    "professional_use":           10,   # declarou uso profissional (Ponto 05)
    "hobby_use":                 -20,   # declarou hobby (Ponto 05)

    # --- Prejuízo financeiro (Ponto 06) ---
    "monthly_loss_above_5k":      20,   # prejuízo mensal acima de R$ 5.000
    "monthly_loss_1k_to_5k":      10,
    "monthly_loss_below_1k":       0,
    "no_financial_loss":         -10,

    # --- Qualidade do perfil (Ponto 02) ---
    "blank_or_personal_bio":     -10,
    "no_monetization_signal":    -15,

    # --- Gravidade do problema (Ponto 01 e 03) ---
    "permanent_ban":              10,   # banimento permanente — urgência maior
    "temporary_restriction":       5,   # restrição temporária
    "warning_only":                0,   # apenas aviso

    # --- Origem do lead ---
    "referral_lead":              10,   # veio por indicação — priorizar
    "existing_client":            10,   # cliente da casa
}

# ---------------------------------------------------------------------------
# Níveis de qualificação
# ---------------------------------------------------------------------------
QUALIFICATION_LEVELS = {
    (60, 100): "hot",
    (30, 59):  "warm",
    (5,  29):  "cold",
    (-100, 4): "disqualified",
}

ACTION_MAP = {
    "auto_meeting":  "Agendar reunião imediatamente — bypass de qualificação",
    "hot":           "Agendar reunião imediatamente",
    "warm":          "Oferecer reunião ou nutrir com follow-up",
    "cold":          "Sequência de follow-up — 3 contatos",
    "disqualified":  "Arquivar lead — reativar em 6 meses se perfil mudar",
}


@dataclass
class QualificationResult:
    score: int
    level: str
    recommended_action: str
    auto_meeting: bool
    events: list[dict] = field(default_factory=list)


def calculate_score(signals: list[str]) -> QualificationResult:
    """Calcula score de qualificação a partir dos sinais coletados nos 6 pontos DRX.

    Verifica primeiro se há sinais de reunião automática (300k+ ou profissional
    que monetiza). Se sim, retorna auto_meeting=True independente do score total.
    """
    # 1. Verificar sinais de reunião automática
    triggered = AUTO_MEETING_SIGNALS.intersection(signals)
    if triggered:
        return QualificationResult(
            score=100,
            level="auto_meeting",
            recommended_action=ACTION_MAP["auto_meeting"],
            auto_meeting=True,
            events=[{"signal": s, "delta": 100, "score_after": 100} for s in triggered],
        )

    # 2. Calcular score pelos sinais restantes
    score = 0
    events = []

    for signal in signals:
        delta = SCORING_MATRIX.get(signal, 0)
        if delta != 0:
            score += delta
            events.append({"signal": signal, "delta": delta, "score_after": score})

    score = max(-100, min(100, score))

    # 3. Determinar nível
    level = "disqualified"
    for (low, high), lvl in QUALIFICATION_LEVELS.items():
        if low <= score <= high:
            level = lvl
            break

    return QualificationResult(
        score=score,
        level=level,
        recommended_action=ACTION_MAP[level],
        auto_meeting=False,
        events=events,
    )
