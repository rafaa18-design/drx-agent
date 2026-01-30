"""Tool para obter data e hora atual com referências temporais."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from agno.tools import tool

DIAS_DA_SEMANA = [
    'Segunda-feira',
    'Terça-feira',
    'Quarta-feira',
    'Quinta-feira',
    'Sexta-feira',
    'Sábado',
    'Domingo',
]


@tool
def obter_data_hora() -> str:
    """Retorna a data e hora atual em São Paulo com referências temporais úteis para agendamento."""
    tz = ZoneInfo('America/Sao_Paulo')
    agora = datetime.now(tz)

    amanha = agora + timedelta(days=1)
    depois_amanha = agora + timedelta(days=2)
    proxima_semana = agora + timedelta(days=7)
    quinze_dias = agora + timedelta(days=15)
    um_mes = agora + timedelta(days=30)
    tres_meses = agora + timedelta(days=90)

    def fmt(d: datetime) -> str:
        dia_semana = DIAS_DA_SEMANA[d.weekday()]
        return f'{dia_semana} dia {d.strftime("%d/%m/%Y")}'

    hora = agora.strftime('%H:%M')
    data = agora.strftime('%d/%m/%Y')
    dia_semana_hoje = DIAS_DA_SEMANA[agora.weekday()]

    return (
        f'A hora atual é {hora} e a data é {data}, '
        f'hoje o dia da semana é {dia_semana_hoje}.\n'
        f'A próxima {dia_semana_hoje} será dia {proxima_semana.strftime("%d/%m/%Y")}.\n'
        f'Amanhã é {fmt(amanha)}.\n'
        f'Depois de amanhã é {fmt(depois_amanha)}.\n'
        f'Daqui a 15 dias será {fmt(quinze_dias)}.\n'
        f'Daqui a 1 mês será {fmt(um_mes)}.\n'
        f'Daqui a 3 meses será {fmt(tres_meses)}.'
    )
