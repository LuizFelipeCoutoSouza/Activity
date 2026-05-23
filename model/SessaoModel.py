"""
model/SessaoModel.py — Operações de banco para a tabela `sessoes`.

Cada sessão é identificada por um UUID aleatório e tem uma data de expiração.
Permite manter o usuário autenticado entre refreshes de página via cookie.
"""

import uuid
from datetime import datetime, timedelta

from model.database import get_connection


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
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO sessoes (token, usuario_id, expira_em) VALUES (%s, %s, %s);",
                (token, usuario_id, expira_em),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        return token

    @staticmethod
    def buscar_usuario_id(token: str) -> int | None:
        """Retorna o usuario_id se o token for válido e não expirado; None caso contrário."""
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT usuario_id FROM sessoes WHERE token = %s AND expira_em > NOW();",
                (token,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()
        return row[0] if row else None

    @staticmethod
    def deletar(token: str) -> None:
        """Remove a sessão do banco (logout ou invalidação manual)."""
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM sessoes WHERE token = %s;", (token,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
