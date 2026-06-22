"""Camada de acesso a dados da tabela `arquivos`.

Operações de banco puras para os arquivos `.txt` de actigrafia enviados pelos
usuários. Todos os métodos filtram por `usuario_id`, garantindo isolamento entre
usuários. Consumido exclusivamente pelo `ArquivoController`.
"""

from __future__ import annotations

from model.database import db_cursor


class ArquivoModel:
    """Operações de persistência para arquivos de actigrafia."""

    @staticmethod
    def salvar(usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo) -> int:
        """Insere um novo arquivo e retorna seu id.

        Args:
            usuario_id: Id do usuário dono do arquivo.
            nome: Nome do arquivo.
            descricao: Descrição livre.
            tamanho_bytes: Tamanho do conteúdo em bytes.
            num_linhas: Número de linhas do arquivo, ou None se desconhecido.
            encoding: Encoding detectado do arquivo.
            conteudo: Conteúdo binário completo (BYTEA).

        Returns:
            int: Id do arquivo recém-criado.
        """
        with db_cursor(write=True) as cur:
            cur.execute("""
                INSERT INTO arquivos (usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (usuario_id, nome, descricao, tamanho_bytes, num_linhas, encoding, conteudo))
            return cur.fetchone()[0]

    @staticmethod
    def listar(usuario_id) -> list[dict]:
        """Lista os arquivos de um usuário (metadados, sem o conteúdo binário).

        Resultado ordenado da criação mais recente para a mais antiga.

        Args:
            usuario_id: Id do usuário dono dos arquivos.

        Returns:
            list[dict]: Lista de metadados de arquivo.
        """
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
        """Busca um arquivo completo (incluindo o conteúdo binário).

        Args:
            arquivo_id: Id do arquivo.
            usuario_id: Id do usuário dono (filtro de isolamento).

        Returns:
            dict | None: Dados do arquivo com `conteudo`, ou None se não existir
            ou não pertencer ao usuário.
        """
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
        """Busca um arquivo de um usuário pelo nome, sem diferenciar maiúsculas.

        Usado para detectar nomes duplicados antes de um upload.

        Args:
            usuario_id: Id do usuário dono.
            nome: Nome a procurar (comparação case-insensitive).

        Returns:
            dict | None: Dicionário com o `id` do arquivo encontrado, ou None.
        """
        with db_cursor(dict_row=True) as cur:
            cur.execute(
                "SELECT id FROM arquivos WHERE usuario_id = %s AND LOWER(nome) = LOWER(%s);",
                (usuario_id, nome),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def atualizar_metadados(arquivo_id, usuario_id, nome, descricao):
        """Atualiza nome e descrição de um arquivo, registrando `atualizado_em`.

        Args:
            arquivo_id: Id do arquivo.
            usuario_id: Id do usuário dono (filtro de isolamento).
            nome: Novo nome.
            descricao: Nova descrição.
        """
        with db_cursor(write=True) as cur:
            cur.execute("""
                UPDATE arquivos
                SET nome = %s, descricao = %s, atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s AND usuario_id = %s;
            """, (nome, descricao, arquivo_id, usuario_id))

    @staticmethod
    def substituir_conteudo(arquivo_id, usuario_id, nome, descricao,
                            tamanho_bytes, num_linhas, encoding, conteudo):
        """Substitui o conteúdo e os metadados de um arquivo existente.

        Args:
            arquivo_id: Id do arquivo a substituir.
            usuario_id: Id do usuário dono (filtro de isolamento).
            nome: Novo nome.
            descricao: Nova descrição.
            tamanho_bytes: Novo tamanho em bytes.
            num_linhas: Novo número de linhas, ou None.
            encoding: Novo encoding.
            conteudo: Novo conteúdo binário (BYTEA).
        """
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
        """Remove um arquivo do usuário.

        Args:
            arquivo_id: Id do arquivo a remover.
            usuario_id: Id do usuário dono (filtro de isolamento).
        """
        with db_cursor(write=True) as cur:
            cur.execute(
                "DELETE FROM arquivos WHERE id = %s AND usuario_id = %s;",
                (arquivo_id, usuario_id),
            )
