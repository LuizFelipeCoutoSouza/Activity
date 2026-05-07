from model.database import get_connection
from psycopg2.extras import RealDictCursor
import bcrypt

class UserModel:

    # CREATE
    @staticmethod
    def criar_usuario(nome, email, cpf, senha, profissao):
        senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO usuarios (nome, email, cpf, senha, profissao)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (nome, email, cpf, senha_hash, profissao))
            user_id = cursor.fetchone()[0]
            conn.commit()
            return user_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    # READ (todos)
    @staticmethod
    def listar_usuarios():
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, nome, email, cpf, profissao, criado_em FROM usuarios;")
        usuarios = cursor.fetchall()
        cursor.close()
        conn.close()
        return usuarios

    # READ (por id)
    @staticmethod
    def buscar_por_id(user_id):
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, nome, email, cpf, profissao FROM usuarios WHERE id = %s;",
            (user_id,)
        )
        usuario = cursor.fetchone()
        cursor.close()
        conn.close()
        return usuario

    # UPDATE
    @staticmethod
    def atualizar_usuario(user_id, nome, email, cpf, profissao):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE usuarios
                SET nome=%s, email=%s, cpf=%s, profissao=%s
                WHERE id=%s;
            """, (nome, email, cpf, profissao, user_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    # DELETE
    @staticmethod
    def deletar_usuario(user_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM usuarios WHERE id=%s;", (user_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()