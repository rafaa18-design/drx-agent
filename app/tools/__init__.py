"""Ferramentas do agente de atendimento.

Tools agrupadas por domínio:
- consultas: agendar, cancelar, verificar disponibilidade (template base)
- pacientes: buscar, histórico, verificar cliente, convênios (template base)
- catalogo: listar serviços, calcular orçamento, obter data/hora (template base)
- sessao: salvar dados cliente, salvar preferências, ver contexto (template base)
- drx: leads, calendar, whatsapp, qualification (DRX Advogados)
"""

from app.tools.catalogo import calcular_orcamento, listar_servicos, obter_data_hora
from app.tools.consultas import agendar_consulta, cancelar_consulta, verificar_disponibilidade
from app.tools.drx import (
    book_appointment,
    check_availability,
    escalate_to_human,
    get_lead_context,
    qualify_lead,
    send_whatsapp_message,
    update_lead_status,
)
from app.tools.formatar_contexto import formatar_contexto_completo, formatar_contexto_state
from app.tools.pacientes import (
    buscar_paciente,
    consultar_convenios,
    consultar_historico_paciente,
    verificar_cliente,
)
from app.tools.sessao import salvar_dados_cliente, salvar_preferencias, ver_contexto_sessao

__all__ = [
    # Template base
    "listar_servicos",
    "verificar_disponibilidade",
    "agendar_consulta",
    "cancelar_consulta",
    "buscar_paciente",
    "consultar_historico_paciente",
    "consultar_convenios",
    "calcular_orcamento",
    "salvar_dados_cliente",
    "salvar_preferencias",
    "ver_contexto_sessao",
    "verificar_cliente",
    "formatar_contexto_state",
    "formatar_contexto_completo",
    "obter_data_hora",
    # DRX Advogados
    "qualify_lead",
    "get_lead_context",
    "update_lead_status",
    "check_availability",
    "book_appointment",
    "send_whatsapp_message",
    "escalate_to_human",
]
