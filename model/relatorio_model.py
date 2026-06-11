from model.database import db_cursor


class RelatorioModel:

    @staticmethod
    def salvar(usuario_id, nome, arquivo_origem, tamanho_bytes, conteudo) -> int:
        with db_cursor(write=True) as cur:
            cur.execute("""
                INSERT INTO relatorios (usuario_id, nome, arquivo_origem, tamanho_bytes, conteudo)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (usuario_id, nome, arquivo_origem, tamanho_bytes, conteudo))
            return cur.fetchone()[0]

    @staticmethod
    def listar(usuario_id) -> list[dict]:
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
        with db_cursor(write=True) as cur:
            cur.execute(
                "DELETE FROM relatorios WHERE id = %s AND usuario_id = %s;",
                (relatorio_id, usuario_id),
            )
