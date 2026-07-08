"""OAuth 2.0 do Google Calendar — cada advogado conecta a própria conta.

Substitui a abordagem antiga de service account + domain-wide delegation
(que exigia Google Workspace). Aqui, cada advogado autoriza o app a acessar
o próprio Google Calendar via tela de consentimento padrão do Google —
funciona com qualquer conta, inclusive Gmail pessoal grátis.
"""

import os

from cryptography.fernet import Fernet, InvalidToken

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "auth_uri": _AUTH_URI,
            "token_uri": _TOKEN_URI,
            "redirect_uris": [os.environ["GOOGLE_OAUTH_REDIRECT_URI"]],
        }
    }


def build_flow():
    """Monta o Flow OAuth em memória — sem precisar de client_secret.json em disco."""
    from google_auth_oauthlib.flow import Flow

    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=os.environ["GOOGLE_OAUTH_REDIRECT_URI"],
    )


def get_authorization_url(state: str) -> str:
    """URL de consentimento do Google para o advogado autorizar o acesso ao Calendar."""
    flow = build_flow()
    # prompt="consent" garante um refresh_token mesmo em reconexões (o Google só
    # devolve refresh_token na primeira autorização, a menos que force o consent).
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=state,
    )
    return auth_url


def exchange_code(code: str) -> dict:
    """Troca o code de autorização por tokens; retorna refresh_token e e-mail da conta."""
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token as google_id_token

    flow = build_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    account_email = None
    if credentials.id_token:
        claims = google_id_token.verify_oauth2_token(
            credentials.id_token, GoogleRequest(), os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        )
        account_email = claims.get("email")

    return {
        "refresh_token": credentials.refresh_token,
        "account_email": account_email,
    }


def _fernet() -> Fernet:
    key = os.environ["LAWYER_TOKEN_ENCRYPTION_KEY"]
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_refresh_token(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_refresh_token(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError("Não foi possível decriptar o refresh token — LAWYER_TOKEN_ENCRYPTION_KEY mudou?") from e
