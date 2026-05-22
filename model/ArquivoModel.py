from model.database import get_connection
from psycopg2.extras import RealDictCursor


class ArquivoModel:

    @staticmethod
    def salvar(usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO arquivos (usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo))
            arquivo_id = cursor.fetchone()[0]
            conn.commit()
            return arquivo_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def listar(usuario_id):
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, nome, descricao, tamanho_bytes, num_linhas, encoding, criado_em, atualizado_em
            FROM arquivos
            WHERE usuario_id = %s
            ORDER BY criado_em DESC;
        """, (usuario_id,))
        arquivos = cursor.fetchall()
        cursor.close()
        conn.close()
        return arquivos

    @staticmethod
    def buscar(arquivo_id, usuario_id):
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo, criado_em, atualizado_em
            FROM arquivos
            WHERE id = %s AND usuario_id = %s;
        """, (arquivo_id, usuario_id))
        arquivo = cursor.fetchone()
        cursor.close()
        conn.close()
        return arquivo

    @staticmethod
    def atualizar_metadados(arquivo_id, usuario_id, nome, descricao):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE arquivos
                SET nome = %s, descricao = %s, atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s AND usuario_id = %s;
            """, (nome, descricao, arquivo_id, usuario_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def substituir_conteudo(arquivo_id, usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE arquivos
                SET nome = %s, descricao = %s, tamanho_bytes = %s, num_linhas = %s,
                    encoding = %s, conteudo = %s, atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s AND usuario_id = %s;
            """, (nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo, arquivo_id, usuario_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def buscar_por_nome(usuario_id, nome):
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id FROM arquivos WHERE usuario_id = %s AND LOWER(nome) = LOWER(%s);",
            (usuario_id, nome)
        )
        resultado = cursor.fetchone()
        cursor.close()
        conn.close()
        return resultado

    @staticmethod
    def deletar(arquivo_id, usuario_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM arquivos WHERE id = %s AND usuario_id = %s;",
                (arquivo_id, usuario_id)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
