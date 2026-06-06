from model.database import get_connection
from psycopg2.extras import RealDictCursor


class PacienteModel:

    @staticmethod
    def criar(usuario_id, nome, sexo, data_nascimento, email, telefone, altura, peso, nota) -> int:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO pacientes
                    (usuario_id, nome, sexo, data_nascimento, email, telefone, altura, peso, nota)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (usuario_id, nome, sexo, data_nascimento, email, telefone, altura, peso, nota))
            pid = cursor.fetchone()[0]
            conn.commit()
            return pid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def listar(usuario_id) -> list:
        conn   = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT p.*, COUNT(pa.arquivo_id) AS num_arquivos
            FROM pacientes p
            LEFT JOIN paciente_arquivos pa ON p.id = pa.paciente_id
            WHERE p.usuario_id = %s
            GROUP BY p.id
            ORDER BY p.nome;
        """, (usuario_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows

    @staticmethod
    def buscar(paciente_id, usuario_id) -> dict | None:
        conn   = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT * FROM pacientes WHERE id = %s AND usuario_id = %s;",
            (paciente_id, usuario_id),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def atualizar(paciente_id, usuario_id, nome, sexo, data_nascimento,
                  email, telefone, altura, peso, nota):
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE pacientes
                SET nome=%s, sexo=%s, data_nascimento=%s, email=%s, telefone=%s,
                    altura=%s, peso=%s, nota=%s, atualizado_em=CURRENT_TIMESTAMP
                WHERE id=%s AND usuario_id=%s;
            """, (nome, sexo, data_nascimento, email, telefone,
                  altura, peso, nota, paciente_id, usuario_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def deletar(paciente_id, usuario_id):
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM pacientes WHERE id=%s AND usuario_id=%s;",
                (paciente_id, usuario_id),
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    # ── Vínculo com arquivos ──────────────────────────────────────────────────

    @staticmethod
    def listar_arquivos(paciente_id) -> list:
        conn   = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT a.id AS arquivo_id, a.nome, a.tamanho_bytes, a.num_linhas
            FROM paciente_arquivos pa
            JOIN arquivos a ON pa.arquivo_id = a.id
            WHERE pa.paciente_id = %s
            ORDER BY a.nome;
        """, (paciente_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows

    @staticmethod
    def listar_arquivos_ocupados(usuario_id: int, paciente_id_atual: int) -> list:
        """Retorna arquivos vinculados a OUTROS pacientes do mesmo usuário."""
        conn   = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT pa.arquivo_id, a.nome AS arquivo_nome, p.nome AS paciente_nome
            FROM paciente_arquivos pa
            JOIN arquivos  a ON pa.arquivo_id  = a.id
            JOIN pacientes p ON pa.paciente_id = p.id
            WHERE p.usuario_id = %s AND pa.paciente_id != %s;
        """, (usuario_id, paciente_id_atual))
        rows = [dict(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows

    @staticmethod
    def listar_arquivos_ocupados_por_ids(arquivo_ids: set) -> list:
        """Retorna os arquivos do conjunto que já estão vinculados a algum paciente."""
        if not arquivo_ids:
            return []
        conn   = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT pa.arquivo_id, a.nome AS arquivo_nome, p.nome AS paciente_nome
            FROM paciente_arquivos pa
            JOIN arquivos  a ON pa.arquivo_id  = a.id
            JOIN pacientes p ON pa.paciente_id = p.id
            WHERE pa.arquivo_id = ANY(%s);
        """, (list(arquivo_ids),))
        rows = [dict(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows

    @staticmethod
    def vincular_arquivo(paciente_id, arquivo_id):
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO paciente_arquivos (paciente_id, arquivo_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (paciente_id, arquivo_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def desvincular_arquivo(paciente_id, arquivo_id):
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM paciente_arquivos WHERE paciente_id=%s AND arquivo_id=%s;",
                (paciente_id, arquivo_id),
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
