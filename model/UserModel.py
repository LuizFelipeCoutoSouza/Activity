"""
model/UserModel.py — Camada de acesso a dados da tabela `usuarios`.

Senhas armazenadas com hash bcrypt. Colunas BYTEA (foto_perfil) são convertidas
para bytes pelo helper interno `_row`.
"""

import bcrypt

from model.database import db_cursor


class UserModel:

    @staticmethod
    def _row(row) -> dict | None:
        """Converte RealDictRow em dict, transformando BYTEA em bytes."""
        if row is None:
            return None
        d = dict(row)
        if d.get("foto_perfil") is not None:
            d["foto_perfil"] = bytes(d["foto_perfil"])
        return d

    @staticmethod
    def criar_usuario(nome, email, cpf, senha, profissao) -> int:
        senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
        with db_cursor(write=True) as cur:
            cur.execute("""
                INSERT INTO usuarios (nome, email, cpf, senha, profissao)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (nome, email, cpf, senha_hash, profissao))
            return cur.fetchone()[0]

    @staticmethod
    def listar_usuarios() -> list:
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, email, cpf, profissao, telefone,
                       data_nascimento, bio, criado_em
                FROM usuarios;
            """)
            return [UserModel._row(r) for r in cur.fetchall()]

    @staticmethod
    def buscar_por_id(user_id) -> dict | None:
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, email, cpf, profissao, telefone,
                       data_nascimento, bio, foto_perfil, foto_nome, foto_tipo, criado_em
                FROM usuarios WHERE id = %s;
            """, (user_id,))
            return UserModel._row(cur.fetchone())

    @staticmethod
    def buscar_por_email(email) -> dict | None:
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, email, cpf, senha, profissao, telefone,
                       data_nascimento, bio, foto_perfil, foto_nome, foto_tipo
                FROM usuarios WHERE email = %s;
            """, (email,))
            return UserModel._row(cur.fetchone())

    @staticmethod
    def buscar_senha(user_id) -> str | None:
        with db_cursor() as cur:
            cur.execute("SELECT senha FROM usuarios WHERE id = %s;", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None

    @staticmethod
    def atualizar_perfil(user_id, nome, email, cpf, profissao,
                         telefone, data_nascimento, bio):
        with db_cursor(write=True) as cur:
            cur.execute("""
                UPDATE usuarios
                SET nome=%s, email=%s, cpf=%s, profissao=%s,
                    telefone=%s, data_nascimento=%s, bio=%s
                WHERE id=%s;
            """, (nome, email, cpf, profissao,
                  telefone or None, data_nascimento, bio or None, user_id))

    @staticmethod
    def atualizar_foto(user_id, foto_bytes, foto_nome, foto_tipo):
        with db_cursor(write=True) as cur:
            cur.execute("""
                UPDATE usuarios
                SET foto_perfil=%s, foto_nome=%s, foto_tipo=%s
                WHERE id=%s;
            """, (foto_bytes, foto_nome, foto_tipo, user_id))

    @staticmethod
    def atualizar_senha(user_id, nova_senha_hash):
        with db_cursor(write=True) as cur:
            cur.execute(
                "UPDATE usuarios SET senha=%s WHERE id=%s;",
                (nova_senha_hash, user_id),
            )

    @staticmethod
    def deletar_usuario(user_id):
        with db_cursor(write=True) as cur:
            cur.execute("DELETE FROM usuarios WHERE id=%s;", (user_id,))