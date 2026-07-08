"""Servidor mock local — serve dados de exemplo para o dashboard DRX sem depender do Postgres.

O banco de produção (Railway) está inacessível no momento (conexão recusada
pelo servidor). Este mock roda na porta 8000 — mesma porta que o backend
real usa — e implementa os endpoints que o CRM (drx-crm) consome, devolvendo
os mesmos 12 leads de exemplo definidos em scripts/seed_demo_data.py.

Uso:
    uv run scripts/mock_dashboard_server.py
    # depois abra o CRM normalmente (npm run dev na pasta drx-crm) —
    # NEXT_PUBLIC_API_URL já aponta para http://localhost:8000

Isso é só para visualização local. Quando o banco do Railway voltar,
pare este mock e rode o backend real (uvicorn app.main:app) + o script
de seed de verdade para persistir os dados.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="DRX Mock Dashboard Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

now = datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return now - timedelta(days=n)


def days_from_now(n: int) -> datetime:
    return now + timedelta(days=n)


# ─────────────────────────────────────────────────────────────────────────────
# Dados de exemplo — mesmos 12 leads do seed_demo_data.py
# ─────────────────────────────────────────────────────────────────────────────

_RAW_LEADS = [
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
        appointment=dict(days_offset=-5, status="completed"),
        escalated=True,
    ),
]

PHONE_PREFIX = "551190000"

LEADS: list[dict] = []
APPOINTMENTS: list[dict] = []
CONVERSATIONS: list[dict] = []

# Hora de chegada de cada lead curado (varia o heatmap dia × hora do dashboard)
_CURATED_HOURS = [9, 14, 11, 19, 10, 16, 20, 13, 15, 9, 18, 11]

for i, data in enumerate(_RAW_LEADS, start=1):
    lead_id = str(uuid.uuid4())
    phone = f"{PHONE_PREFIX}{i:03d}"
    created = days_ago(data["days_created"]).replace(
        hour=_CURATED_HOURS[(i - 1) % len(_CURATED_HOURS)], minute=(i * 17) % 60
    )
    if created > now:
        created -= timedelta(days=1)
    updated = days_ago(max(data["days_created"] - 1, 0))

    LEADS.append({
        "id": lead_id,
        "phone": phone,
        "name": data["name"],
        "email": None,
        "platform": data["platform"],
        "case_type": data["case_type"],
        "case_description": data["case_description"],
        "monthly_loss_estimate": data["monthly_loss_estimate"],
        "qualification_score": data["qualification_score"],
        "qualification_level": data["qualification_level"],
        "qualification_signals": data["qualification_signals"],
        "commercial_status": data["commercial_status"],
        "source": data["source"],
        "assigned_to": "seed-demo",
        "ai_active": True,
        "ai_silenced_until": None,
        "follow_up_count": 0,
        "follow_up_last_sent_at": None,
        "created_at": created,
        "updated_at": updated,
    })

    conv_status = "human_required" if data.get("escalated") else "active"
    CONVERSATIONS.append({
        "id": str(uuid.uuid4()),
        "lead_id": lead_id,
        "lead_name": data["name"],
        "lead_phone": phone,
        "channel": "whatsapp",
        "status": conv_status,
        "ai_handoff_reason": "Cliente solicitou falar com advogado" if data.get("escalated") else None,
        "started_at": created,
        "last_message_at": updated,
        "closed_at": None,
    })

    appt_data = data.get("appointment")
    if appt_data:
        scheduled_at = (
            days_from_now(appt_data["days_offset"])
            if appt_data["days_offset"] >= 0
            else days_ago(-appt_data["days_offset"])
        )
        APPOINTMENTS.append({
            "id": str(uuid.uuid4()),
            "lead_id": lead_id,
            "lead_name": data["name"],
            "lead_phone": phone,
            "lawyer_id": None,
            "google_event_id": None,
            "google_meet_link": "https://meet.google.com/exemplo-demo" if appt_data["status"] != "completed" else None,
            "scheduled_at": scheduled_at,
            "duration_minutes": 60,
            "status": appt_data["status"],
            "appointment_type": "initial_consultation",
            "notes": "Agendamento de exemplo (mock).",
            "created_at": created,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Leads históricos gerados — dão densidade aos gráficos do dashboard
# (determinístico: mesma seed → mesmos dados a cada restart)
# ─────────────────────────────────────────────────────────────────────────────

_rng = random.Random(42)

_HIST_FIRST = [
    "Ana", "Bruno", "Carla", "Diego", "Elisa", "Felipe", "Gabriela", "Heitor",
    "Isabela", "Jonas", "Karina", "Leandro", "Mariana", "Nathan", "Otávio",
    "Priscila", "Renata", "Samuel", "Tainá", "Vitor", "Yasmin", "Bárbara",
    "Caio", "Débora",
]
_HIST_LAST = [
    "Almeida", "Barbosa", "Cardoso", "Diniz", "Esteves", "Fonseca",
    "Guimarães", "Junqueira", "Lacerda", "Moreira", "Nunes", "Oliveira",
    "Pires", "Queiroz", "Ramos", "Sales", "Teixeira", "Uchoa", "Vasconcelos",
    "Werneck",
]
_HIST_PLATFORMS = ["instagram"] * 4 + ["tiktok"] * 3 + ["youtube"] * 2 + ["facebook"] * 1
_HIST_CASES = ["permanent_ban", "temporary_restriction", "warning_only"]
_HIST_LEVELS = [
    # (nível, faixa de score, peso)
    ("auto_meeting", (95, 100), 1),
    ("hot", (60, 90), 3),
    ("warm", (35, 55), 4),
    ("cold", (5, 25), 3),
    ("disqualified", (-50, -10), 2),
]
# Horas do dia ponderadas: picos no meio da manhã e início da noite
_HIST_HOURS = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
_HIST_HOUR_W = [2, 5, 6, 6, 4, 3, 4, 4, 4, 4, 5, 7, 8, 6, 3]


def _hist_status(level: str, age_days: int) -> str:
    """Destino no funil coerente com o nível e a idade do lead."""
    if level == "disqualified":
        return "lost"
    if age_days >= 10:
        if level in ("auto_meeting", "hot"):
            return _rng.choice(["won", "won", "follow_up", "lost"])
        return _rng.choice(["lost", "lost", "follow_up", "won"])
    if age_days >= 5:
        return _rng.choice(["qualified", "proposal", "contacted", "follow_up"])
    return _rng.choice(["new", "contacted", "contacted", "qualified"])


_hist_names: set[str] = set()
for j in range(48):
    while True:
        name = f"{_rng.choice(_HIST_FIRST)} {_rng.choice(_HIST_LAST)}"
        if name not in _hist_names:
            _hist_names.add(name)
            break

    level, (lo, hi), _w = _rng.choices(_HIST_LEVELS, weights=[w for *_ , w in _HIST_LEVELS])[0]
    age = _rng.randint(0, 29)
    created = (now - timedelta(days=age)).replace(
        hour=_rng.choices(_HIST_HOURS, weights=_HIST_HOUR_W)[0],
        minute=_rng.randint(0, 59),
    )
    # Fim de semana tem menos movimento: 60% dos leads migram para quinta/sexta
    if created.weekday() >= 5 and _rng.random() < 0.6:
        created -= timedelta(days=2)
    if created > now:
        created -= timedelta(days=1)
    updated = min(created + timedelta(hours=_rng.randint(2, 72)), now)

    LEADS.append({
        "id": str(uuid.uuid4()),
        "phone": f"{PHONE_PREFIX}{j + 13:03d}",
        "name": name,
        "email": None,
        "platform": _rng.choice(_HIST_PLATFORMS),
        "case_type": _rng.choice(_HIST_CASES),
        "case_description": "Lead histórico de demonstração.",
        "monthly_loss_estimate": None,
        "qualification_score": _rng.randint(lo, hi),
        "qualification_level": level,
        "qualification_signals": {"signals": []},
        "commercial_status": _hist_status(level, age),
        "source": _rng.choice(["ad", "ad", "referral", "unknown"]),
        "assigned_to": "seed-demo",
        "ai_active": True,
        "ai_silenced_until": None,
        "follow_up_count": 0,
        "follow_up_last_sent_at": None,
        "created_at": created,
        "updated_at": updated,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Leads
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/leads")
def list_leads(
    status: str | None = Query(None),
    source: str | None = Query(None),
    level: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
):
    items = LEADS
    if status:
        items = [l for l in items if l["commercial_status"] == status]
    if source:
        items = [l for l in items if l["source"] == source]
    if level:
        items = [l for l in items if l["qualification_level"] == level]
    if search:
        s = search.lower()
        items = [l for l in items if s in (l["name"] or "").lower() or s in l["phone"]]

    total = len(items)
    return {"items": items[offset:offset + limit], "total": total}


@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: str):
    for l in LEADS:
        if l["id"] == lead_id:
            return l
    return {"error": "not found"}


@app.patch("/api/leads/{lead_id}")
def update_lead(lead_id: str, body: dict):
    for l in LEADS:
        if l["id"] == lead_id:
            l.update(body)
            l["updated_at"] = now
            return l
    return {"error": "not found"}


@app.post("/api/leads/{lead_id}/toggle-ai")
def toggle_ai(lead_id: str):
    for l in LEADS:
        if l["id"] == lead_id:
            l["ai_active"] = not l["ai_active"]
            l["updated_at"] = now
            return {"lead_id": lead_id, "ai_active": l["ai_active"]}
    return {"error": "not found"}


@app.delete("/api/leads/{lead_id}", status_code=204)
def delete_lead(lead_id: str):
    global LEADS
    LEADS = [l for l in LEADS if l["id"] != lead_id]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Appointments
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/appointments")
def list_appointments(
    status: str | None = Query(None),
    lead_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    items = APPOINTMENTS
    if status:
        items = [a for a in items if a["status"] == status]
    if lead_id:
        items = [a for a in items if a["lead_id"] == lead_id]

    items = sorted(items, key=lambda a: a["scheduled_at"], reverse=True)
    total = len(items)
    return {"items": items[offset:offset + limit], "total": total}


@app.get("/api/appointments/calendar/availability")
def get_availability(date: str = Query(...), duration: int = Query(60)):
    return {"available_slots": [], "date": date, "duration_minutes": duration}


# ─────────────────────────────────────────────────────────────────────────────
# Conversations
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/conversations")
def list_conversations(status: str | None = Query(None)):
    items = CONVERSATIONS
    if status:
        items = [c for c in items if c["status"] == status]
    items = sorted(items, key=lambda c: c["last_message_at"], reverse=True)
    return {"items": items, "total": len(items)}


@app.post("/api/conversations/{conv_id}/reply")
def reply_conversation(conv_id: str, body: dict):
    for c in CONVERSATIONS:
        if c["id"] == conv_id:
            c["last_message_at"] = datetime.now(timezone.utc)
            if c["status"] == "human_required":
                c["status"] = "active"
            return {"ok": True, "message_id": str(uuid.uuid4())}
    return {"error": "not found"}


# ─────────────────────────────────────────────────────────────────────────────
# Follow-up
# ─────────────────────────────────────────────────────────────────────────────

_FU_MESSAGES = {
    1: "Boa tarde {nome}, tudo bem? Conseguiu verificar os pontos que alinhamos para dar seguimento no serviço?",
    2: "Boa tarde {nome}. Imagino que esteja na correria, e por isso ainda não retornou. Saiba que estamos disponíveis para regularizar a sua conta, conte conosco.",
    3: "Me parece que regularizar sua conta não é mais uma prioridade para você. Entendo seu momento, mas comunico que iremos encerrar nossos contatos. Não é uma porta que se fecha, saiba que continuamos a disposição.",
}
_FU_MIN_DAYS = {1: 3, 2: 6, 3: 14}


@app.get("/api/follow-up")
def list_follow_ups():
    rows = []
    for lead in LEADS:
        if lead["commercial_status"] != "proposal" or lead["follow_up_count"] >= 3:
            continue

        last_appt = None
        for a in APPOINTMENTS:
            if a["lead_id"] == lead["id"] and a["status"] != "cancelled":
                if last_appt is None or a["scheduled_at"] > last_appt["scheduled_at"]:
                    last_appt = a

        next_fu = lead["follow_up_count"] + 1
        days_since = (now - last_appt["scheduled_at"]).days if last_appt else 0
        min_days = _FU_MIN_DAYS.get(next_fu, 99)
        eligible = days_since >= min_days
        nome = lead["name"] or "cliente"

        rows.append({
            "lead_id": lead["id"],
            "lead_name": lead["name"],
            "lead_phone": lead["phone"],
            "qualification_score": lead["qualification_score"],
            "qualification_level": lead["qualification_level"],
            "commercial_status": lead["commercial_status"],
            "follow_up_count": lead["follow_up_count"],
            "follow_up_last_sent_at": lead.get("follow_up_last_sent_at"),
            "next_fu_number": next_fu,
            "next_fu_message": _FU_MESSAGES.get(next_fu, "").format(nome=nome),
            "days_since_meeting": days_since,
            "eligible": eligible,
            "last_appointment_at": last_appt["scheduled_at"] if last_appt else None,
        })

    rows.sort(key=lambda r: r["qualification_score"], reverse=True)
    return {"items": rows, "total": len(rows)}


@app.post("/api/follow-up/{lead_id}/send")
def mark_follow_up_sent(lead_id: str):
    for l in LEADS:
        if l["id"] == lead_id:
            l["follow_up_count"] += 1
            l["follow_up_last_sent_at"] = now
            if l["follow_up_count"] >= 3:
                l["commercial_status"] = "lost"
            return {
                "lead_id": lead_id,
                "follow_up_count": l["follow_up_count"],
                "commercial_status": l["commercial_status"],
                "message": f"FU0{l['follow_up_count']} registrado com sucesso.",
            }
    return {"error": "not found"}


@app.post("/api/follow-up/{lead_id}/responded")
def mark_lead_responded(lead_id: str):
    for l in LEADS:
        if l["id"] == lead_id:
            l["commercial_status"] = "qualified"
            l["ai_active"] = True
            return {
                "lead_id": lead_id,
                "commercial_status": l["commercial_status"],
                "message": "Lead retornou ao funil ativo.",
            }
    return {"error": "not found"}


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/dashboard/kpis")
def get_kpis():
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    leads_month = sum(1 for l in LEADS if l["created_at"] >= start_of_month)
    appts_month = sum(1 for a in APPOINTMENTS if a["created_at"] >= start_of_month and a["status"] != "cancelled")

    total_leads = len(LEADS) or 1
    won_leads = sum(1 for l in LEADS if l["commercial_status"] == "won")
    conversion_rate = won_leads / total_leads

    total_convs = len(CONVERSATIONS) or 1
    escalated = sum(1 for c in CONVERSATIONS if c["status"] == "human_required")
    escalation_rate = escalated / total_convs

    ai_active = sum(1 for l in LEADS if l["ai_active"])
    ai_inactive = sum(1 for l in LEADS if not l["ai_active"])

    return {
        "leads_this_month": leads_month,
        "appointments_scheduled": appts_month,
        "conversion_rate": round(conversion_rate, 4),
        "escalation_rate": round(escalation_rate, 4),
        "ai_active_leads": ai_active,
        "ai_inactive_leads": ai_inactive,
        "total_leads": len(LEADS),
    }


@app.get("/api/dashboard/funnel")
def get_funnel():
    stages_order = ["new", "contacted", "qualified", "proposal", "won", "lost"]
    counts: dict[str, int] = {}
    for l in LEADS:
        counts[l["commercial_status"]] = counts.get(l["commercial_status"], 0) + 1

    return {"stages": [{"stage": s, "count": counts.get(s, 0)} for s in stages_order]}


@app.get("/api/dashboard/agent-metrics")
def get_agent_metrics():
    total = len(LEADS) or 1
    levels = {lvl: sum(1 for l in LEADS if l["qualification_level"] == lvl)
              for lvl in ("auto_meeting", "hot", "warm", "cold", "disqualified")}
    avg_score = sum(l["qualification_score"] for l in LEADS) / total

    return {
        "total_qualified": len(LEADS),
        "auto_meeting": levels["auto_meeting"],
        "hot": levels["hot"],
        "warm": levels["warm"],
        "cold": levels["cold"],
        "disqualified": levels["disqualified"],
        "average_score": round(avg_score, 1),
    }


@app.get("/api/dashboard/appointments")
def get_appointment_metrics():
    next_7 = now + timedelta(days=7)
    upcoming = sum(1 for a in APPOINTMENTS if now <= a["scheduled_at"] <= next_7 and a["status"] == "scheduled")
    completed = sum(1 for a in APPOINTMENTS if a["status"] == "completed")
    cancelled = sum(1 for a in APPOINTMENTS if a["status"] == "cancelled")
    no_show = sum(1 for a in APPOINTMENTS if a["status"] == "no_show")

    return {
        "upcoming_7_days": upcoming,
        "completed": completed,
        "cancelled": cancelled,
        "no_show": no_show,
    }


@app.get("/health")
def health():
    return {"status": "ok", "mode": "mock", "leads": len(LEADS)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
