"""Seed de dados de exemplo para o dashboard CRM DRX Advogados.

Cria leads, conversas, mensagens e agendamentos fictícios cobrindo todos os
níveis de qualificação (auto_meeting, hot, warm, cold, disqualified) e
estágios do pipeline comercial, para popular o dashboard com dados realistas.

IMPORTANTE — NÃO EXECUTADO AUTOMATICAMENTE. Este script grava no banco
apontado por DATABASE_URL (.env). Se esse banco for o mesmo usado pelo
agente Tiago em produção, os leads de exemplo abaixo ficarão misturados
com leads reais de clientes.

Todos os leads criados aqui têm assigned_to="seed-demo" e telefones no
padrão 5511900000XXX (claramente fictício) — isso permite limpar tudo
depois com o comando de cleanup.

Usa psycopg (síncrono) em vez de asyncpg — asyncpg tem um bug conhecido de
SSL handshake no Windows (ConnectionResetError / connection_lost) que não
ocorre com psycopg.

Uso:
    uv run scripts/seed_demo_data.py            # insere os dados de exemplo
    uv run scripts/seed_demo_data.py --cleanup  # remove tudo que foi inserido
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import create_engine, select, delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models import Appointment, Conversation, Lead, Message  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Engine síncrono (psycopg) — evita o bug de SSL do asyncpg no Windows
# ─────────────────────────────────────────────────────────────────────────────

_raw_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL", "")
for _prefix in ("postgresql+asyncpg://", "postgresql://"):
    if _raw_url.startswith(_prefix):
        _raw_url = "postgresql+psycopg://" + _raw_url[len(_prefix):]
        break

engine = create_engine(_raw_url, echo=False, pool_pre_ping=True)

SEED_MARKER = "seed-demo"
PHONE_PREFIX = "551190000"  # + 3 dígitos sequenciais → 5511900000001, ...

now = datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return now - timedelta(days=n)


def days_from_now(n: int) -> datetime:
    return now + timedelta(days=n)


# ─────────────────────────────────────────────────────────────────────────────
# Dados de exemplo — 12 leads cobrindo todos os níveis e estágios
# ─────────────────────────────────────────────────────────────────────────────

LEADS = [
    # ── auto_meeting (bypass de score — 300k+ ou profissional monetizador) ──
    dict(
        name="Camila Nogueira", platform="instagram", case_type="permanent_ban",
        case_description="Conta banida por suposta violação de propriedade intelectual.",
        monthly_loss_estimate=18000.0, qualification_score=100, qualification_level="auto_meeting",
        qualification_signals={"signals": ["followers_300k_plus", "professional_bio_with_link", "verified_badge"]},
        commercial_status="proposal", source="ad", days_created=2,
        appointment=dict(days_offset=3, status="scheduled"),
    ),
    dict(
        name="Dr. Rafael Menezes", platform="youtube", case_type="temporary_restriction",
        case_description="Monetização suspensa — canal de nutrição com 120k inscritos.",
        monthly_loss_estimate=9500.0, qualification_score=100, qualification_level="auto_meeting",
        qualification_signals={"signals": ["professional_monetizer", "high_ticket_profession", "monetization_history"]},
        commercial_status="won", source="referral", days_created=18,
        appointment=dict(days_offset=-10, status="completed"),
    ),

    # ── hot (60-100) ──
    dict(
        name="Bianca Ferraz", platform="tiktok", case_type="permanent_ban",
        case_description="Banimento definitivo alegando conteúdo impróprio — perfil de moda.",
        monthly_loss_estimate=7200.0, qualification_score=75, qualification_level="hot",
        qualification_signals={"signals": ["followers_100k_to_300k", "professional_bio_with_link", "digital_marketing", "monthly_loss_above_5k"]},
        commercial_status="qualified", source="ad", days_created=5,
        appointment=dict(days_offset=2, status="scheduled"),
    ),
    dict(
        name="Thiago Aquino", platform="instagram", case_type="permanent_ban",
        case_description="Conta de e-commerce banida — vendas paradas há 2 semanas.",
        monthly_loss_estimate=6000.0, qualification_score=65, qualification_level="hot",
        qualification_signals={"signals": ["followers_100k_to_300k", "verified_badge", "monthly_loss_1k_to_5k", "permanent_ban"]},
        commercial_status="contacted", source="ad", days_created=1,
    ),

    # ── warm (30-59) ──
    dict(
        name="Larissa Prado", platform="instagram", case_type="temporary_restriction",
        case_description="Restrição temporária de 30 dias em perfil de estética.",
        monthly_loss_estimate=2500.0, qualification_score=45, qualification_level="warm",
        qualification_signals={"signals": ["followers_10k_to_100k", "professional_use", "monthly_loss_1k_to_5k"]},
        commercial_status="qualified", source="referral", days_created=8,
    ),
    dict(
        name="Eduardo Salles", platform="tiktok", case_type="warning_only",
        case_description="Recebeu aviso de violação de diretrizes — criador de conteúdo fitness.",
        monthly_loss_estimate=1800.0, qualification_score=35, qualification_level="warm",
        qualification_signals={"signals": ["followers_10k_to_100k", "digital_marketing", "warning_only"]},
        commercial_status="new", source="unknown", days_created=0,
    ),

    # ── cold (5-29) ──
    dict(
        name="Patrícia Lemos", platform="youtube", case_type="temporary_restriction",
        case_description="Restrição de monetização — canal pequeno de receitas.",
        monthly_loss_estimate=600.0, qualification_score=15, qualification_level="cold",
        qualification_signals={"signals": ["followers_10k_to_100k", "monthly_loss_below_1k", "blank_or_personal_bio"]},
        commercial_status="follow_up", source="unknown", days_created=12,
    ),
    dict(
        name="Vinícius Costa", platform="instagram", case_type="warning_only",
        case_description="Aviso de conteúdo — perfil pessoal com alguma monetização esporádica.",
        monthly_loss_estimate=300.0, qualification_score=10, qualification_level="cold",
        qualification_signals={"signals": ["followers_5k_to_10k", "no_financial_loss", "warning_only"]},
        commercial_status="new", source="unknown", days_created=3,
    ),

    # ── disqualified (< 5 — menos de 10k seguidores ou hobby) ──
    dict(
        name="Juliana Rocha", platform="tiktok", case_type="temporary_restriction",
        case_description="Conta pessoal, poucos seguidores, uso de hobby.",
        monthly_loss_estimate=None, qualification_score=-50, qualification_level="disqualified",
        qualification_signals={"signals": ["followers_below_5k", "hobby_use"]},
        commercial_status="lost", source="unknown", days_created=25,
    ),
    dict(
        name="Marcos Villela", platform="instagram", case_type="warning_only",
        case_description="Perfil pessoal, sem intuito comercial, apenas aviso recebido.",
        monthly_loss_estimate=None, qualification_score=-40, qualification_level="disqualified",
        qualification_signals={"signals": ["followers_below_5k", "hobby_use", "no_monetization_signal"]},
        commercial_status="lost", source="unknown", days_created=30,
    ),

    # ── conversas ainda em qualificação / escalada para humano ──
    dict(
        name="Fernanda Duarte", platform="instagram", case_type="permanent_ban",
        case_description="Cliente insistindo em falar com advogado sobre processo já aberto.",
        monthly_loss_estimate=4200.0, qualification_score=55, qualification_level="warm",
        qualification_signals={"signals": ["followers_10k_to_100k", "professional_use", "monthly_loss_1k_to_5k"]},
        commercial_status="qualified", source="existing_client", days_created=4,
        escalated=True,
    ),
    dict(
        name="Gustavo Amaral", platform="youtube", case_type="permanent_ban",
        case_description="Canal de marketing digital banido — quer prazo urgente.",
        monthly_loss_estimate=11000.0, qualification_score=70, qualification_level="hot",
        qualification_signals={"signals": ["followers_100k_to_300k", "digital_marketing", "monthly_loss_above_5k"]},
        commercial_status="proposal", source="ad", days_created=6,
        appointment=dict(days_offset=5, status="scheduled"),
        escalated=True,
    ),
]

CONVERSATION_MESSAGES = [
    ("inbound", "client", "Boa tarde, minha conta foi banida e preciso de ajuda urgente."),
    ("outbound", "ai", "Boa tarde! Aqui é o assistente do Tiago, da DRX Advogados. Me conta o que aconteceu, pode mandar o print do problema?"),
    ("inbound", "client", "Recebi uma mensagem de banimento definitivo, não sei o motivo."),
    ("outbound", "ai", "Entendi, obrigado por compartilhar. Só pra eu entender melhor o cenário, quantos seguidores você tem aproximadamente?"),
]


def seed(session: Session) -> None:
    for i, data in enumerate(LEADS, start=1):
        phone = f"{PHONE_PREFIX}{i:03d}"

        lead = Lead(
            phone=phone,
            name=data["name"],
            email=None,
            platform=data["platform"],
            case_type=data["case_type"],
            case_description=data["case_description"],
            monthly_loss_estimate=data["monthly_loss_estimate"],
            qualification_score=data["qualification_score"],
            qualification_level=data["qualification_level"],
            qualification_signals=data["qualification_signals"],
            commercial_status=data["commercial_status"],
            source=data["source"],
            assigned_to=SEED_MARKER,
            ai_active=True,
            created_at=days_ago(data["days_created"]),
            updated_at=days_ago(max(data["days_created"] - 1, 0)),
        )
        session.add(lead)
        session.flush()  # garante lead.id

        conv_status = "human_required" if data.get("escalated") else "active"
        conversation = Conversation(
            lead_id=lead.id,
            channel="whatsapp",
            status=conv_status,
            ai_handoff_reason="Cliente solicitou falar com advogado" if data.get("escalated") else None,
            started_at=days_ago(data["days_created"]),
            last_message_at=days_ago(max(data["days_created"] - 1, 0)),
        )
        session.add(conversation)
        session.flush()

        base_time = days_ago(data["days_created"])
        for offset, (direction, sender, content) in enumerate(CONVERSATION_MESSAGES):
            session.add(Message(
                conversation_id=conversation.id,
                direction=direction,
                sender=sender,
                content_type="text",
                content=content,
                created_at=base_time + timedelta(minutes=offset * 3),
            ))

        appt_data = data.get("appointment")
        if appt_data:
            scheduled_at = days_from_now(appt_data["days_offset"]) if appt_data["days_offset"] >= 0 else days_ago(-appt_data["days_offset"])
            session.add(Appointment(
                lead_id=lead.id,
                scheduled_at=scheduled_at,
                duration_minutes=60,
                status=appt_data["status"],
                appointment_type="initial_consultation",
                notes="Agendamento de exemplo (seed-demo).",
                created_at=days_ago(data["days_created"]),
            ))

    session.commit()
    print(f"{len(LEADS)} leads de exemplo criados (assigned_to='{SEED_MARKER}').")


def cleanup(session: Session) -> None:
    ids = session.execute(select(Lead.id).where(Lead.assigned_to == SEED_MARKER)).scalars().all()
    if not ids:
        print("Nenhum lead de exemplo encontrado para remover.")
        return

    # Cascade (conversations → messages, appointments) já configurado no modelo Lead.
    session.execute(delete(Lead).where(Lead.assigned_to == SEED_MARKER))
    session.commit()
    print(f"{len(ids)} leads de exemplo removidos (com conversas/mensagens/agendamentos em cascata).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed de dados de exemplo para o dashboard DRX.")
    parser.add_argument("--cleanup", action="store_true", help="Remove todos os dados de exemplo inseridos.")
    args = parser.parse_args()

    with Session(engine) as session:
        if args.cleanup:
            cleanup(session)
        else:
            seed(session)


if __name__ == "__main__":
    main()
