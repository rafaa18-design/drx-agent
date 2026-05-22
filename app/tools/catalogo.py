"""Tools de catálogo: listar serviços, calcular orçamento e obter data/hora."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.runtime import RetryAgentRun, tool

from app.tools._mock_data import CONVENIOS, SERVICOS


@tool
def listar_servicos() -> str:
    """Lista todos os serviços odontológicos disponíveis na clínica com preços e duração.

    Use esta ferramenta quando o paciente perguntar sobre serviços, procedimentos,
    preços ou o que a clínica oferece.

    Returns:
        Lista formatada de todos os serviços com preço e duração.
    """
    linhas = ["Serviços disponíveis na Clínica Sorriso:\n"]
    for key, s in SERVICOS.items():
        preco = f"R$ {s['preco']:.2f}" if s["preco"] > 0 else "Gratuito"
        linhas.append(
            f"• {s['nome']} ({key}): {preco} | {s['duracao_min']} min\n"
            f"  {s['descricao']}"
        )
    return "\n".join(linhas)


@tool
def calcular_orcamento(servicos: str, convenio: str = "") -> str:
    """Calcula o orçamento para um ou mais serviços, com ou sem convênio.

    Use esta ferramenta para dar ao paciente uma estimativa de valores.

    Args:
        servicos: Lista de serviços separados por vírgula (ex: "limpeza,restauracao,canal").
        convenio: Nome do convênio do paciente (ex: "OdontoPrev"). Deixe vazio para particular.

    Returns:
        Orçamento detalhado com valores por serviço e total.
    """
    lista_servicos = [s.strip().lower() for s in servicos.split(",")]

    # Validar serviços
    invalidos = [s for s in lista_servicos if s not in SERVICOS]
    if invalidos:
        servicos_validos = ", ".join(SERVICOS.keys())
        raise RetryAgentRun(
            f'Serviços não encontrados: {", ".join(invalidos)}. '
            f"Serviços disponíveis: {servicos_validos}"
        )

    # Validar convênio
    conv_info = None
    if convenio:
        for nome_conv, info in CONVENIOS.items():
            if convenio.lower() in nome_conv.lower():
                conv_info = info
                break
        if not conv_info:
            nomes = ", ".join(CONVENIOS.keys())
            raise RetryAgentRun(
                f'Convênio "{convenio}" não encontrado. '
                f"Convênios aceitos: {nomes}. "
                "Deixe vazio para orçamento particular."
            )

    linhas = ["💰 Orçamento - Clínica Sorriso\n"]
    if conv_info:
        linhas.append(f"🏥 Convênio: {conv_info['nome']}\n")
    else:
        linhas.append("👤 Particular (10% desconto à vista)\n")

    total_bruto = 0.0
    total_final = 0.0
    duracao_total = 0

    for s_key in lista_servicos:
        s_info = SERVICOS[s_key]
        preco = s_info["preco"]
        total_bruto += preco
        duracao_total += s_info["duracao_min"]

        if conv_info:
            cobertura = conv_info["cobertura"].get(s_key, 0.0)
            desconto = preco * cobertura
            valor_paciente = preco - desconto
            total_final += valor_paciente
            if cobertura > 0:
                linhas.append(
                    f"• {s_info['nome']}: R$ {preco:.2f} "
                    f"(convênio cobre {int(cobertura * 100)}%) "
                    f"→ R$ {valor_paciente:.2f}"
                )
            else:
                linhas.append(
                    f"• {s_info['nome']}: R$ {preco:.2f} (sem cobertura)"
                )
                total_final += 0  # já somou acima
        else:
            total_final += preco
            preco_str = f"R$ {preco:.2f}" if preco > 0 else "Gratuito"
            linhas.append(f"• {s_info['nome']}: {preco_str}")

    linhas.append(f"\n{'─' * 35}")

    if conv_info:
        economia = total_bruto - total_final
        linhas.append(f"Valor total: R$ {total_bruto:.2f}")
        linhas.append(f"Cobertura do convênio: -R$ {economia:.2f}")
        linhas.append(f"Valor do paciente: R$ {total_final:.2f}")
    else:
        desconto_vista = total_final * 0.10
        linhas.append(f"Valor total: R$ {total_final:.2f}")
        linhas.append(f"À vista (10% desc.): R$ {total_final - desconto_vista:.2f}")
        linhas.append(f"Parcelado 3x: 3x R$ {total_final / 3:.2f}")

    linhas.append(f"\n⏱️ Tempo total estimado: {duracao_total} minutos")
    linhas.append("\n⚠️ Valores sujeitos a alteração após avaliação clínica.")

    return "\n".join(linhas)


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
        f'A próxima {dia_semana_hoje} será dia {proxima_semana.strftime("%d/%m/%Y")} (ISO: {proxima_semana.strftime("%Y-%m-%d")}).\n'
        f'Amanhã é {fmt(amanha)} (ISO: {amanha.strftime("%Y-%m-%d")}).\n'
        f'Depois de amanhã é {fmt(depois_amanha)} (ISO: {depois_amanha.strftime("%Y-%m-%d")}).\n'
        f'Daqui a 15 dias será {fmt(quinze_dias)} (ISO: {quinze_dias.strftime("%Y-%m-%d")}).\n'
        f'Daqui a 1 mês será {fmt(um_mes)} (ISO: {um_mes.strftime("%Y-%m-%d")}).\n'
        f'Daqui a 3 meses será {fmt(tres_meses)} (ISO: {tres_meses.strftime("%Y-%m-%d")}).\n'
        f'IMPORTANTE: use sempre o formato ISO (YYYY-MM-DD) ao chamar check_availability.'
    )
