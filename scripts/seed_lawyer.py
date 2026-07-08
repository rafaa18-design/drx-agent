"""Cadastra ou atualiza um advogado na tabela `lawyers`.

O `username` informado aqui precisa também existir em AUTH_USERS (.env), com
senha em hash bcrypt — gere com `uv run scripts/hash_password.py`. É esse
username que liga o login do CRM ao registro do advogado (para saber quem
está clicando em "Conectar Google Calendar" em /settings).

Uso:
    uv run scripts/seed_lawyer.py --name "Dra. Ana Costa" --email ana@drxadvogados.com.br --username ana --default
    uv run scripts/seed_lawyer.py --list
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models import Lawyer  # noqa: E402

_raw_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL", "")
for _prefix in ("postgresql+asyncpg://", "postgresql://"):
    if _raw_url.startswith(_prefix):
        _raw_url = "postgresql+psycopg://" + _raw_url[len(_prefix):]
        break

engine = create_engine(_raw_url, echo=False, pool_pre_ping=True)


def upsert_lawyer(session: Session, name: str, email: str, username: str, is_default: bool) -> Lawyer:
    lawyer = session.execute(select(Lawyer).where(Lawyer.username == username)).scalar_one_or_none()

    if is_default:
        # Só um advogado default por vez — desmarca os demais.
        for other in session.execute(select(Lawyer).where(Lawyer.is_default.is_(True))).scalars():
            other.is_default = False

    if lawyer:
        lawyer.name = name
        lawyer.email = email
        lawyer.is_default = is_default
    else:
        lawyer = Lawyer(name=name, email=email, username=username, is_default=is_default)
        session.add(lawyer)

    session.commit()
    session.refresh(lawyer)
    return lawyer


def list_lawyers(session: Session) -> None:
    lawyers = session.execute(select(Lawyer)).scalars().all()
    if not lawyers:
        print("Nenhum advogado cadastrado ainda.")
        return
    for lw in lawyers:
        status = "conectado" if lw.google_refresh_token_encrypted else "não conectado"
        default = " [padrão]" if lw.is_default else ""
        print(f"- {lw.name} <{lw.email}> username={lw.username} — Google: {status}{default}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cadastra/atualiza advogado (tabela lawyers).")
    parser.add_argument("--name", help="Nome completo do advogado")
    parser.add_argument("--email", help="E-mail do advogado (contato/identificação)")
    parser.add_argument("--username", help="Username de login no CRM — deve existir em AUTH_USERS")
    parser.add_argument("--default", action="store_true", help="Marca como advogado padrão (usado pelo Tiago)")
    parser.add_argument("--list", action="store_true", help="Lista os advogados cadastrados")
    args = parser.parse_args()

    with Session(engine) as session:
        if args.list:
            list_lawyers(session)
            return

        if not (args.name and args.email and args.username):
            parser.error("--name, --email e --username são obrigatórios (ou use --list)")

        lawyer = upsert_lawyer(session, args.name, args.email, args.username, args.default)
        print(f"Advogado '{lawyer.name}' salvo (id={lawyer.id}, default={lawyer.is_default}).")
        print(f"Lembre-se de cadastrar '{args.username}' em AUTH_USERS com senha em hash bcrypt "
              f"(uv run scripts/hash_password.py) para ele conseguir logar no CRM.")


if __name__ == "__main__":
    main()
