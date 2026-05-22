"""Qualification service — persiste scores no banco."""

from app.tools.drx.qualification import QualificationResult, calculate_score


class QualificationService:
    """Orquestra qualificação de leads e persistência do score."""

    async def qualify(self, lead_id: str, signals: list[str], notes: str = "") -> QualificationResult:
        result = calculate_score(signals)
        # TODO: persistir qualification_events e atualizar lead no banco
        return result
