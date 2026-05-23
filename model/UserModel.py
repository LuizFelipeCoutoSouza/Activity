"""
model/UserModel.py — Camada de acesso a dados da tabela `usuarios`.

Cada método abre e fecha sua própria conexão (sem pool). Senhas são
armazenadas com hash bcrypt. Colunas BYTEA (foto_perfil) são convertidas
para bytes pelo helper interno `_row`.
"""

from model.database import get_connection
from psycopg2.extras import RealDictCursor
import bcrypt


class UserModel:

    @staticmethod
    def _row(row):
        """Converte RealDictRow em dict, transformando BYTEA em bytes."""
        if row is None:
            return None
        d = dict(row)
        if d.get("foto_perfil") is not None:
            d["foto_perfil"] = bytes(d["foto_perfil"])
        return d

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
        cursor.execute("""
            SELECT id, nome, email, cpf, profissao, telefone,
                   data_nascimento, bio, criado_em
            FROM usuarios;
        """)
        usuarios = [UserModel._row(r) for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return usuarios

    # READ (por id)
    @staticmethod
    def buscar_por_id(user_id):
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, nome, email, cpf, profissao, telefone,
                   data_nascimento, bio, foto_perfil, foto_nome, foto_tipo, criado_em
            FROM usuarios WHERE id = %s;
        """, (user_id,))
        return UserModel._row(cursor.fetchone())

    # READ (por email)
    @staticmethod
    def buscar_por_email(email):
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, nome, email, cpf, senha, profissao, telefone,
                   data_nascimento, bio, foto_perfil, foto_nome, foto_tipo
            FROM usuarios WHERE email = %s;
        """, (email,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return UserModel._row(row)

    # READ (senha para verificação)
    @staticmethod
    def buscar_senha(user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT senha FROM usuarios WHERE id = %s;", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row[0] if row else None

    # UPDATE perfil completo
    @staticmethod
    def atualizar_perfil(user_id, nome, email, cpf, profissao,
                         telefone, data_nascimento, bio):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE usuarios
                SET nome=%s, email=%s, cpf=%s, profissao=%s,
                    telefone=%s, data_nascimento=%s, bio=%s
                WHERE id=%s;
            """, (nome, email, cpf, profissao,
                  telefone or None, data_nascimento, bio or None, user_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    # UPDATE foto
    @staticmethod
    def atualizar_foto(user_id, foto_bytes, foto_nome, foto_tipo):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE usuarios
                SET foto_perfil=%s, foto_nome=%s, foto_tipo=%s
                WHERE id=%s;
            """, (foto_bytes, foto_nome, foto_tipo, user_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    # UPDATE senha
    @staticmethod
    def atualizar_senha(user_id, nova_senha_hash):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE usuarios SET senha=%s WHERE id=%s;",
                (nova_senha_hash, user_id)
            )
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