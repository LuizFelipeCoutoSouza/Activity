from __future__ import annotations

from model.database import db_cursor


class ArquivoModel:

    @staticmethod
    def salvar(usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo) -> int:
        with db_cursor(write=True) as cur:
            cur.execute("""
                INSERT INTO arquivos (usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo))
            return cur.fetchone()[0]

    @staticmethod
    def listar(usuario_id) -> list[dict]:
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, descricao, tamanho_bytes, num_linhas, encoding, criado_em, atualizado_em
                FROM arquivos
                WHERE usuario_id = %s
                ORDER BY criado_em DESC;
            """, (usuario_id,))
            return [dict(r) for r in cur.fetchall()]

    @staticmethod
    def buscar(arquivo_id, usuario_id) -> dict | None:
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo, criado_em, atualizado_em
                FROM arquivos
                WHERE id = %s AND usuario_id = %s;
            """, (arquivo_id, usuario_id))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def buscar_por_nome(usuario_id, nome) -> dict | None:
        with db_cursor(dict_row=True) as cur:
            cur.execute(
                "SELECT id FROM arquivos WHERE usuario_id = %s AND LOWER(nome) = LOWER(%s);",
                (usuario_id, nome),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def atualizar_metadados(arquivo_id, usuario_id, nome, descricao):
        with db_cursor(write=True) as cur:
            cur.execute("""
                UPDATE arquivos
                SET nome = %s, descricao = %s, atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s AND usuario_id = %s;
            """, (nome, descricao, arquivo_id, usuario_id))

    @staticmethod
    def substituir_conteudo(arquivo_id, usuario_id, nome, descricao,
                            tamanho_bytes, num_linhas, encoding, conteudo):
        with db_cursor(write=True) as cur:
            cur.execute("""
                UPDATE arquivos
                SET nome = %s, descricao = %s, tamanho_bytes = %s, num_linhas = %s,
                    encoding = %s, conteudo = %s, atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s AND usuario_id = %s;
            """, (nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo,
                  arquivo_id, usuario_id))

    @staticmethod
    def deletar(arquivo_id, usuario_id):
        with db_cursor(write=True) as cur:
            cur.execute(
                "DELETE FROM arquivos WHERE id = %s AND usuario_id = %s;",
                (arquivo_id, usuario_id),
            )
