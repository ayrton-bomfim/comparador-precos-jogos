"""Cria ou atualiza o primeiro usuário administrador.

As credenciais são lidas do ambiente para evitar colocar senha no código.
Exemplo no .env:

ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@exemplo.com
ADMIN_PASSWORD=troque-esta-senha

Execução:
    python -m backend.scripts.usuarios.criar_admin
"""

from __future__ import annotations

import os

from ...banco_dados import SessionLocal
from ...modelos import Usuario
from ...seguranca.autenticacao import hash_password


def main() -> None:
    username = os.getenv("ADMIN_USERNAME", "").strip()
    email = os.getenv("ADMIN_EMAIL", "").strip() or None
    password = os.getenv("ADMIN_PASSWORD", "")

    if not username:
        raise SystemExit("ADMIN_USERNAME não configurado no .env.")

    if not password or len(password) < 10:
        raise SystemExit(
            "ADMIN_PASSWORD deve ser configurada e possuir pelo menos 10 caracteres."
        )

    db = SessionLocal()

    try:
        usuario = (
            db.query(Usuario)
            .filter(Usuario.username == username)
            .first()
        )

        if usuario:
            usuario.email = email
            usuario.role = "admin"
            usuario.ativo = True
            usuario.senha_hash = hash_password(password)
            acao = "atualizado"
        else:
            usuario = Usuario(
                username=username,
                email=email,
                senha_hash=hash_password(password),
                role="admin",
                ativo=True,
            )
            db.add(usuario)
            acao = "criado"

        db.commit()
        print(f"Administrador {acao} com sucesso: {username}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
