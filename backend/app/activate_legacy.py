"""Local-only activation of the exact owner explicitly created by migration."""
import argparse
import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.auth_schemas import Credentials, normalize_email
from app.database import engine
from app.models import User
from app.passwords import hash_password


def main():
    parser = argparse.ArgumentParser(description="Ativa o proprietário legado, sem senha em argumentos ou arquivos.")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    email = normalize_email(args.email)
    password = getpass.getpass("Nova senha (8–128 caracteres): ")
    if password != getpass.getpass("Repita a senha: "):
        raise SystemExit("As senhas não conferem.")
    try:
        payload = Credentials(email=email, password=password)
    except ValidationError:
        raise SystemExit("Use um email válido e senha de 8 a 128 caracteres.") from None
    try:
        with Session(engine) as db:
            user = db.scalar(select(User).where(User.email == payload.email).with_for_update())
            if user is None or user.active or user.password_hash is not None:
                raise SystemExit("Não existe conta legada pendente para este email.")
            user.password_hash = hash_password(payload.password.get_secret_value())
            user.active = True
            db.commit()
        print("Conta legada ativada. Faça login na aplicação.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
