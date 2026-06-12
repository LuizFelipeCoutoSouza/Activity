from __future__ import annotations

from model.database import db_cursor


class PacienteModel:

    @staticmethod
    def criar(usuario_id, nome, sexo, data_nascimento, email, telefone, altura, peso, nota) -> int:
        with db_cursor(write=True) as cur:
            cur.execute("""
                INSERT INTO pacientes
                    (usuario_id, nome, sexo, data_nascimento, email, telefone, altura, peso, nota)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (usuario_id, nome, sexo, data_nascimento, email, telefone, altura, peso, nota))
            return cur.fetchone()[0]

    @staticmethod
    def listar(usuario_id) -> list[dict]:
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT p.*, COUNT(pa.arquivo_id) AS num_arquivos
                FROM pacientes p
                LEFT JOIN paciente_arquivos pa ON p.id = pa.paciente_id
                WHERE p.usuario_id = %s
                GROUP BY p.id
                ORDER BY p.nome;
            """, (usuario_id,))
            return [dict(r) for r in cur.fetchall()]

    @staticmethod
    def buscar(paciente_id, usuario_id) -> dict | None:
        with db_cursor(dict_row=True) as cur:
            cur.execute(
                "SELECT * FROM pacientes WHERE id = %s AND usuario_id = %s;",
                (paciente_id, usuario_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def atualizar(paciente_id, usuario_id, nome, sexo, data_nascimento,
                  email, telefone, altura, peso, nota):
        with db_cursor(write=True) as cur:
            cur.execute("""
                UPDATE pacientes
                SET nome=%s, sexo=%s, data_nascimento=%s, email=%s, telefone=%s,
                    altura=%s, peso=%s, nota=%s, atualizado_em=CURRENT_TIMESTAMP
                WHERE id=%s AND usuario_id=%s;
            """, (nome, sexo, data_nascimento, email, telefone,
                  altura, peso, nota, paciente_id, usuario_id))

    @staticmethod
    def deletar(paciente_id, usuario_id):
        with db_cursor(write=True) as cur:
            cur.execute(
                "DELETE FROM pacientes WHERE id=%s AND usuario_id=%s;",
                (paciente_id, usuario_id),
            )

    # ── Vínculo com arquivos ──────────────────────────────────────────────────

    @staticmethod
    def listar_arquivos(paciente_id) -> list[dict]:
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT a.id AS arquivo_id, a.nome, a.tamanho_bytes, a.num_linhas
                FROM paciente_arquivos pa
                JOIN arquivos a ON pa.arquivo_id = a.id
                WHERE pa.paciente_id = %s
                ORDER BY a.nome;
            """, (paciente_id,))
            return [dict(r) for r in cur.fetchall()]

    @staticmethod
    def listar_arquivos_ocupados(usuario_id: int, paciente_id_atual: int) -> list[dict]:
        """Retorna arquivos vinculados a OUTROS pacientes do mesmo usuário."""
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT pa.arquivo_id, a.nome AS arquivo_nome, p.nome AS paciente_nome
                FROM paciente_arquivos pa
                JOIN arquivos  a ON pa.arquivo_id  = a.id
                JOIN pacientes p ON pa.paciente_id = p.id
                WHERE p.usuario_id = %s AND pa.paciente_id != %s;
            """, (usuario_id, paciente_id_atual))
            return [dict(r) for r in cur.fetchall()]

    @staticmethod
    def listar_arquivos_ocupados_por_ids(arquivo_ids: set) -> list[dict]:
        """Retorna os arquivos do conjunto que já estão vinculados a algum paciente."""
        if not arquivo_ids:
            return []
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT pa.arquivo_id, a.nome AS arquivo_nome, p.nome AS paciente_nome
                FROM paciente_arquivos pa
                JOIN arquivos  a ON pa.arquivo_id  = a.id
                JOIN pacientes p ON pa.paciente_id = p.id
                WHERE pa.arquivo_id = ANY(%s);
            """, (list(arquivo_ids),))
            return [dict(r) for r in cur.fetchall()]

    @staticmethod
    def vincular_arquivo(paciente_id, arquivo_id):
        with db_cursor(write=True) as cur:
            cur.execute("""
                INSERT INTO paciente_arquivos (paciente_id, arquivo_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (paciente_id, arquivo_id))

    @staticmethod
    def desvincular_arquivo(paciente_id, arquivo_id):
        with db_cursor(write=True) as cur:
            cur.execute(
                "DELETE FROM paciente_arquivos WHERE paciente_id=%s AND arquivo_id=%s;",
                (paciente_id, arquivo_id),
            )
