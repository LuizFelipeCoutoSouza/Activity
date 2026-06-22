"""Camada de acesso a dados das tabelas `pacientes` e `paciente_arquivos`.

Operações de banco puras para pacientes e seus vínculos com arquivos. Todos os
métodos de paciente filtram por `usuario_id`, garantindo isolamento entre
usuários. A regra "um arquivo pertence a no máximo um paciente" é aplicada pelo
esquema (UNIQUE em `paciente_arquivos.arquivo_id`). Consumido pelo
`PacienteController`.
"""

from __future__ import annotations

from model.database import db_cursor


class PacienteModel:
    """Operações de persistência para pacientes e vínculos com arquivos."""

    @staticmethod
    def criar(usuario_id, nome, sexo, data_nascimento, email, telefone, altura, peso, nota) -> int:
        """Insere um novo paciente e retorna seu id.

        Args:
            usuario_id: Id do usuário (profissional) dono do paciente.
            nome: Nome do paciente.
            sexo: Sexo do paciente.
            data_nascimento: Data de nascimento.
            email: E-mail do paciente.
            telefone: Telefone do paciente.
            altura: Altura em centímetros.
            peso: Peso em quilogramas.
            nota: Anotação livre.

        Returns:
            int: Id do paciente recém-criado.
        """
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
        """Lista os pacientes do usuário com a contagem de arquivos vinculados.

        Resultado ordenado por nome. Cada item inclui a coluna agregada
        `num_arquivos`.

        Args:
            usuario_id: Id do usuário dono dos pacientes.

        Returns:
            list[dict]: Pacientes com `num_arquivos` por linha.
        """
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
        """Busca um paciente pelo id.

        Args:
            paciente_id: Id do paciente.
            usuario_id: Id do usuário dono (filtro de isolamento).

        Returns:
            dict | None: Dados do paciente, ou None se não existir ou não
            pertencer ao usuário.
        """
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
        """Atualiza os dados de um paciente, registrando `atualizado_em`.

        Args:
            paciente_id: Id do paciente a atualizar.
            usuario_id: Id do usuário dono (filtro de isolamento).
            nome: Novo nome.
            sexo: Novo sexo.
            data_nascimento: Nova data de nascimento.
            email: Novo e-mail.
            telefone: Novo telefone.
            altura: Nova altura em centímetros.
            peso: Novo peso em quilogramas.
            nota: Nova anotação livre.
        """
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
        """Remove um paciente.

        Os vínculos em `paciente_arquivos` caem por CASCADE; os arquivos em si
        permanecem (apenas deixam de estar vinculados).

        Args:
            paciente_id: Id do paciente a remover.
            usuario_id: Id do usuário dono (filtro de isolamento).
        """
        with db_cursor(write=True) as cur:
            cur.execute(
                "DELETE FROM pacientes WHERE id=%s AND usuario_id=%s;",
                (paciente_id, usuario_id),
            )

    # ── Vínculo com arquivos ──────────────────────────────────────────────────

    @staticmethod
    def listar_arquivos(paciente_id) -> list[dict]:
        """Lista os arquivos vinculados a um paciente.

        Args:
            paciente_id: Id do paciente.

        Returns:
            list[dict]: Arquivos vinculados, ordenados por nome (campos
            `arquivo_id`, `nome`, `tamanho_bytes`, `num_linhas`).
        """
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
        """Lista arquivos já vinculados a outros pacientes do mesmo usuário.

        Usado para ocultar, na edição de um paciente, os arquivos indisponíveis
        (vinculados a terceiros).

        Args:
            usuario_id: Id do usuário dono.
            paciente_id_atual: Id do paciente em edição, excluído do resultado.

        Returns:
            list[dict]: Itens com `arquivo_id`, `arquivo_nome` e `paciente_nome`.
        """
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
        """Filtra, dentre os ids dados, os arquivos já vinculados a algum paciente.

        Args:
            arquivo_ids: Conjunto de ids de arquivo a verificar.

        Returns:
            list[dict]: Itens com `arquivo_id`, `arquivo_nome` e `paciente_nome`
            para os arquivos do conjunto que já estão vinculados. Lista vazia se
            `arquivo_ids` for vazio.
        """
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
        """Vincula um arquivo a um paciente (idempotente).

        Usa `ON CONFLICT DO NOTHING`: revincular um par já existente não gera erro.

        Args:
            paciente_id: Id do paciente.
            arquivo_id: Id do arquivo a vincular.
        """
        with db_cursor(write=True) as cur:
            cur.execute("""
                INSERT INTO paciente_arquivos (paciente_id, arquivo_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (paciente_id, arquivo_id))

    @staticmethod
    def desvincular_arquivo(paciente_id, arquivo_id):
        """Remove o vínculo entre um paciente e um arquivo.

        Args:
            paciente_id: Id do paciente.
            arquivo_id: Id do arquivo a desvincular.
        """
        with db_cursor(write=True) as cur:
            cur.execute(
                "DELETE FROM paciente_arquivos WHERE paciente_id=%s AND arquivo_id=%s;",
                (paciente_id, arquivo_id),
            )
