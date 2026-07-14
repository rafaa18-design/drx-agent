"""Deteccao de lead vindo de anuncio (Click to WhatsApp Ads).

Sinal forte (se disponivel): campo `ad_referral` repassado pelo conector do
WhatsApp com dados extraidos do payload bruto (ctwa_clid, source_type, etc).
Sinal fraco (fallback, sempre disponivel): a primeira mensagem do lead bate
com um dos textos padrao que a Meta preenche automaticamente no botao
"Enviar mensagem" do anuncio, quando o anunciante nao personalizou esse
texto (muito comum em campanhas de pequenas empresas no Brasil).

Nenhum dos dois sinais e garantido pela Meta/WhatsApp: o objeto `referral`
oficial so existe na Cloud API (app WhatsApp Business oficial), nao no
WhatsApp Web multi-device que provedores como uazapi usam por baixo dos
panos — e o texto padrao pode ser customizado por qualquer anunciante. Por
isso isto e uma heuristica de melhor esforco, nao uma certeza absoluta.
"""

import difflib
import re
import unicodedata

# Variantes ja observadas do texto padrao que a Meta autopreenche no botao
# "Enviar mensagem" de anuncios do Instagram/Facebook (comparadas depois de
# normalizadas — ver _normalize). Adicione novas variantes aqui conforme
# forem aparecendo em campanhas diferentes.
_CTWA_OPENER_TEMPLATES = [
    "ola tenho interesse e desejo mais informacoes por favor",
    "ola tenho interesse e gostaria de mais informacoes por favor",
    "ola tenho interesse e gostaria de saber mais informacoes por favor",
    "oi tenho interesse e gostaria de mais informacoes por favor",
    "hello can i get more info on this",
]

_SIMILARITY_THRESHOLD = 0.85


def _normalize(text: str) -> str:
    """Remove acentos, pontuacao e normaliza espacos/caixa para comparacao."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    t = t.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def looks_like_ad_opener(text: str) -> bool:
    """Compara a primeira mensagem com os textos padrao conhecidos de anuncio.

    Usa similaridade (nao so igualdade exata) para tolerar pequenas variacoes
    de pontuacao/espacamento sem abrir mao de exigir a frase quase inteira —
    combinar so por palavras soltas tipo "interesse" geraria falsos positivos
    com mensagens organicas legitimas.
    """
    normalized = _normalize(text)
    if not normalized:
        return False
    for template in _CTWA_OPENER_TEMPLATES:
        ratio = difflib.SequenceMatcher(None, normalized, template).ratio()
        if ratio >= _SIMILARITY_THRESHOLD:
            return True
    return False


def has_ad_referral(ad_referral: dict | None) -> bool:
    """Sinal forte: metadado de referral repassado pelo conector do WhatsApp."""
    if not ad_referral:
        return False
    return bool(ad_referral.get("source_type") or ad_referral.get("ctwa_clid"))


def is_paid_traffic_opener(text: str, ad_referral: dict | None = None) -> bool:
    """True se algum sinal disponivel indica que a mensagem veio de um anuncio."""
    if has_ad_referral(ad_referral):
        return True
    return looks_like_ad_opener(text)
