"""
model/SessaoModel.py — Operações de banco para a tabela `sessoes`.

Cada sessão é identificada por um UUID aleatório e tem uma data de expiração.
Permite manter o usuário autenticado entre refreshes de página via cookie.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from model.database import db_cursor


class SessaoModel:

    @staticmethod
    def criar(usuario_id: int, dias: int) -> str:
        """Cria uma nova sessão e retorna o token UUID."""
        token     = str(uuid.uuid4())
        expira_em = (
            datetime.now() + timedelta(days=dias)
            if dias > 0
            else datetime.now() + timedelta(hours=2)  # session cookie — expira rápido no banco
        )
        with db_cursor(write=True) as cur:
            cur.execute(
                "INSERT INTO sessoes (token, usuario_id, expira_em) VALUES (%s, %s, %s);",
                (token, usuario_id, expira_em),
            )
        return token

    @staticmethod
    def buscar_usuario_id(token: str) -> int | None:
        """Retorna o usuario_id se o token for válido e não expirado; None caso contrário."""
        with db_cursor() as cur:
            cur.execute(
                "SELECT usuario_id FROM sessoes WHERE token = %s AND expira_em > NOW();",
                (token,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    @staticmethod
    def deletar(token: str) -> None:
        """Remove a sessão do banco (logout ou invalidação manual)."""
        with db_cursor(write=True) as cur:
            cur.execute("DELETE FROM sessoes WHERE token = %s;", (token,))
