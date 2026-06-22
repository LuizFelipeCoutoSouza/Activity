"""Camada de acesso a dados da tabela `sessoes`.

Cada sessão é identificada por um token UUID aleatório e possui data de expiração.
Sustenta a persistência de login entre refreshes de página: o token é guardado em
um cookie no navegador e revalidado contra esta tabela a cada carregamento.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from model.database import db_cursor


class SessaoModel:
    """Operações de persistência para sessões de autenticação."""

    @staticmethod
    def criar(usuario_id: int, dias: int) -> str:
        """Cria uma sessão para o usuário e retorna o token gerado.

        Args:
            usuario_id: Id do usuário autenticado.
            dias: Validade desejada em dias. Se for maior que 0, a sessão expira
                em `dias` dias ("manter conectado"). Se for 0, equivale a um
                session cookie e expira em 2 horas no banco.

        Returns:
            str: Token UUID v4 da sessão criada.
        """
        token     = str(uuid.uuid4())
        # dias == 0 → session cookie: validade curta no banco por segurança.
        expira_em = (
            datetime.now() + timedelta(days=dias)
            if dias > 0
            else datetime.now() + timedelta(hours=2)
        )
        with db_cursor(write=True) as cur:
            cur.execute(
                "INSERT INTO sessoes (token, usuario_id, expira_em) VALUES (%s, %s, %s);",
                (token, usuario_id, expira_em),
            )
        return token

    @staticmethod
    def buscar_usuario_id(token: str) -> int | None:
        """Resolve um token de sessão para o id do usuário, validando a expiração.

        Args:
            token: Token UUID da sessão.

        Returns:
            int | None: Id do usuário se o token existir e não estiver expirado;
            None caso contrário.
        """
        with db_cursor() as cur:
            cur.execute(
                "SELECT usuario_id FROM sessoes WHERE token = %s AND expira_em > NOW();",
                (token,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    @staticmethod
    def deletar(token: str) -> None:
        """Remove a sessão do banco (logout ou invalidação manual).

        Args:
            token: Token UUID da sessão a remover.
        """
        with db_cursor(write=True) as cur:
            cur.execute("DELETE FROM sessoes WHERE token = %s;", (token,))
