# -----------------------------------------------------------------------------
# Activity — Sistema web para análise de dados de actigrafia
#
# Monografia apresentada à Escola de Artes, Ciências e Humanidades da
# Universidade de São Paulo, como parte dos requisitos exigidos na disciplina
# ACH2017 — Projeto Supervisionado ou de Graduação I, para obtenção do título
# de Bacharelado em Sistemas de Informação.
#
# Modalidade: TCC curto (1 semestre) — em grupo
#
# Autores:
#   Laila Malafaia Vieira
#   Luiz Felipe Couto de Souza
#
# Orientadora: Profa. Dra. Ana Amélia Benedito Silva
#
# São Paulo, 2026
# -----------------------------------------------------------------------------

"""Camada de acesso a dados da tabela `usuarios`.

Contém operações de banco puras (sem validação de negócio), consumidas pelo
`UserController`. As senhas são armazenadas com hash bcrypt e as colunas BYTEA
(`foto_perfil`) são convertidas de `memoryview` para `bytes` pelo helper interno
`_row`.
"""

from __future__ import annotations

import bcrypt

from model.database import db_cursor


class UserModel:
    """Operações de persistência para usuários."""

    @staticmethod
    def _row(row) -> dict | None:
        """Normaliza uma linha do banco para um dicionário Python comum.

        Args:
            row: Linha retornada por um cursor com `RealDictCursor`, ou None.

        Returns:
            dict | None: Dicionário com os campos do usuário, com `foto_perfil`
            convertida de `memoryview` para `bytes`; None se `row` for None.
        """
        if row is None:
            return None
        d = dict(row)
        if d.get("foto_perfil") is not None:
            d["foto_perfil"] = bytes(d["foto_perfil"])
        return d

    @staticmethod
    def criar_usuario(nome, email, cpf, senha, profissao) -> int:
        """Insere um novo usuário, gerando o hash bcrypt da senha.

        Args:
            nome: Nome completo do usuário.
            email: E-mail (único na tabela).
            cpf: CPF (único na tabela).
            senha: Senha em texto puro; é convertida em hash bcrypt antes de gravar.
            profissao: Profissão do usuário.

        Returns:
            int: Id do usuário recém-criado.
        """
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
        """Lista todos os usuários, sem campos sensíveis (senha, foto).

        Returns:
            list[dict]: Lista de usuários com dados de perfil básicos.
        """
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, email, cpf, profissao, telefone,
                       data_nascimento, bio, criado_em
                FROM usuarios;
            """)
            return [UserModel._row(r) for r in cur.fetchall()]

    @staticmethod
    def buscar_por_id(user_id) -> dict | None:
        """Busca o perfil completo de um usuário pelo id (inclui foto, sem senha).

        Args:
            user_id: Id do usuário.

        Returns:
            dict | None: Dados do perfil, ou None se não houver usuário com esse id.
        """
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, email, cpf, profissao, telefone,
                       data_nascimento, bio, foto_perfil, foto_nome, foto_tipo, criado_em
                FROM usuarios WHERE id = %s;
            """, (user_id,))
            return UserModel._row(cur.fetchone())

    @staticmethod
    def buscar_por_email(email) -> dict | None:
        """Busca um usuário pelo e-mail, incluindo o hash da senha.

        Diferente de `buscar_por_id`, retorna a coluna `senha` por ser usada na
        autenticação por e-mail.

        Args:
            email: E-mail do usuário.

        Returns:
            dict | None: Dados do usuário (com `senha`), ou None se não encontrado.
        """
        with db_cursor(dict_row=True) as cur:
            cur.execute("""
                SELECT id, nome, email, cpf, senha, profissao, telefone,
                       data_nascimento, bio, foto_perfil, foto_nome, foto_tipo
                FROM usuarios WHERE email = %s;
            """, (email,))
            return UserModel._row(cur.fetchone())

    @staticmethod
    def buscar_senha(user_id) -> str | None:
        """Retorna apenas o hash de senha de um usuário.

        Args:
            user_id: Id do usuário.

        Returns:
            str | None: Hash bcrypt da senha, ou None se o usuário não existir.
        """
        with db_cursor() as cur:
            cur.execute("SELECT senha FROM usuarios WHERE id = %s;", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None

    @staticmethod
    def atualizar_perfil(user_id, nome, email, cpf, profissao,
                         telefone, data_nascimento, bio):
        """Atualiza os dados de perfil de um usuário.

        Campos de texto vazios em `telefone` e `bio` são gravados como NULL.

        Args:
            user_id: Id do usuário a atualizar.
            nome: Novo nome.
            email: Novo e-mail.
            cpf: Novo CPF.
            profissao: Nova profissão.
            telefone: Telefone (string vazia vira NULL).
            data_nascimento: Data de nascimento.
            bio: Biografia (string vazia vira NULL).
        """
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
        """Grava a foto de perfil de um usuário.

        Args:
            user_id: Id do usuário.
            foto_bytes: Conteúdo binário da imagem (BYTEA).
            foto_nome: Nome do arquivo de imagem.
            foto_tipo: Tipo MIME da imagem (ex.: ``image/png``).
        """
        with db_cursor(write=True) as cur:
            cur.execute("""
                UPDATE usuarios
                SET foto_perfil=%s, foto_nome=%s, foto_tipo=%s
                WHERE id=%s;
            """, (foto_bytes, foto_nome, foto_tipo, user_id))

    @staticmethod
    def atualizar_senha(user_id, nova_senha_hash):
        """Atualiza o hash de senha de um usuário.

        Args:
            user_id: Id do usuário.
            nova_senha_hash: Novo hash bcrypt já calculado pelo chamador.
        """
        with db_cursor(write=True) as cur:
            cur.execute(
                "UPDATE usuarios SET senha=%s WHERE id=%s;",
                (nova_senha_hash, user_id),
            )

    @staticmethod
    def deletar_usuario(user_id):
        """Remove um usuário do banco.

        Args:
            user_id: Id do usuário a remover.
        """
        with db_cursor(write=True) as cur:
            cur.execute("DELETE FROM usuarios WHERE id=%s;", (user_id,))