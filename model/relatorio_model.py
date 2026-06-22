"""Camada de acesso a dados da tabela `relatorios`.

Operações de banco puras para os relatórios exportados (arquivos `.zip`) salvos
por usuário. Todos os métodos filtram por `usuario_id`. Consumido pelo
`RelatorioController`.
"""

from __future__ import annotations

from model.database import db_cursor


class RelatorioModel:
    """Operações de persistência para relatórios exportados."""

    @staticmethod
    def salvar(usuario_id, nome, arquivo_origem, tamanho_bytes, conteudo) -> int:
        """Insere um novo relatório exportado e retorna seu id.

        Args:
            usuario_id: Id do usuário dono do relatório.
            nome: Nome do arquivo `.zip` exportado.
            arquivo_origem: Nome do arquivo `.txt` que originou a exportação.
            tamanho_bytes: Tamanho do `.zip` em bytes.
            conteudo: Conteúdo binário do `.zip` (BYTEA).

        Returns:
            int: Id do relatório recém-criado.
        """
        with db_cursor(write=True) as cur:
            cur.execute("""
                INSERT INTO relatorios (usuario_id, nome, arquivo_origem, tamanho_bytes, conteudo)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (usuario_id, nome, arquivo_origem, tamanho_bytes, conteudo))
            return cur.fetchone()[0]

    @staticmethod
    def listar(usuario_id) -> list[dict]:
        """Lista os relatórios de um usuário (metadados, sem o conteúdo binário).

        Resultado ordenado da criação mais recente para a mais antiga.

        Args:
            usuario_id: Id do usuário dono dos relatórios.

        Returns:
            list[dict]: Lista de metadados de relatório.
        """
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, arquivo_origem, tamanho_bytes, criado_em
                FROM relatorios
                WHERE usuario_id = %s
                ORDER BY criado_em DESC;
            """, (usuario_id,))
            return [dict(r) for r in cur.fetchall()]

    @staticmethod
    def buscar(relatorio_id, usuario_id) -> dict | None:
        """Busca um relatório completo (incluindo o conteúdo binário).

        Args:
            relatorio_id: Id do relatório.
            usuario_id: Id do usuário dono (filtro de isolamento).

        Returns:
            dict | None: Dados do relatório com `conteudo`, ou None se não existir
            ou não pertencer ao usuário.
        """
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, arquivo_origem, tamanho_bytes, conteudo, criado_em
                FROM relatorios
                WHERE id = %s AND usuario_id = %s;
            """, (relatorio_id, usuario_id))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def deletar(relatorio_id, usuario_id):
        """Remove um relatório do usuário.

        Args:
            relatorio_id: Id do relatório a remover.
            usuario_id: Id do usuário dono (filtro de isolamento).
        """
        with db_cursor(write=True) as cur:
            cur.execute(
                "DELETE FROM relatorios WHERE id = %s AND usuario_id = %s;",
                (relatorio_id, usuario_id),
            )
