"""Ferramentas do agente de atendimento.

Cada tool está em seu próprio arquivo dentro de app/tools/.
Este módulo re-exporta todas as tools para manter a interface de import.

⚠️  IMPORTANTE: As tools deste template usam dados mockados (_mock_data.py)
para desenvolvimento e testes. Em produção, substitua por integrações reais
(APIs, bancos de dados, serviços externos).
"""

from app.tools.agendar_consulta import agendar_consulta
from app.tools.buscar_paciente import buscar_paciente
from app.tools.calcular_orcamento import calcular_orcamento
from app.tools.cancelar_consulta import cancelar_consulta
from app.tools.consultar_convenios import consultar_convenios
from app.tools.consultar_historico import consultar_historico_paciente
from app.tools.formatar_contexto import formatar_contexto_state
from app.tools.listar_servicos import listar_servicos
from app.tools.obter_data_hora import obter_data_hora
from app.tools.salvar_dados_cliente import salvar_dados_cliente
from app.tools.salvar_preferencias import salvar_preferencias
from app.tools.ver_contexto_sessao import ver_contexto_sessao
from app.tools.verificar_cliente import verificar_cliente
from app.tools.verificar_disponibilidade import verificar_disponibilidade

__all__ = [
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
    "obter_data_hora",
]
