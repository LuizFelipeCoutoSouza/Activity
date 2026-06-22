"""Conexão com o banco de dados PostgreSQL e inicialização do esquema.

Este módulo é a única fonte de verdade para acesso à conexão. Expõe o utilitário
de conexão (`get_connection`), o context manager de cursor usado por toda a camada
de modelos (`db_cursor`) e a rotina idempotente de criação do esquema (`init_db`).

As credenciais são lidas de variáveis de ambiente com defaults voltados ao
desenvolvimento local (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
"""

import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    """Abre e retorna uma conexão psycopg2 com o PostgreSQL.

    Os parâmetros de conexão são lidos das variáveis de ambiente `DB_HOST`,
    `DB_NAME`, `DB_USER`, `DB_PASSWORD` e `DB_PORT`, com defaults locais.

    Returns:
        psycopg2.extensions.connection: Conexão bruta com o banco. Cabe ao
        chamador fechá-la (ou usar `db_cursor`, que cuida disso).
    """
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "Activity"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        port=os.environ.get("DB_PORT", "5432"),
    )


@contextmanager
def db_cursor(write: bool = False, dict_row: bool = False):
    """Fornece um cursor psycopg2 com gestão automática de transação e recursos.

    No fim do bloco, comita (se `write`), faz rollback em caso de exceção e
    sempre fecha cursor e conexão.

    Args:
        write: Se True, comita ao sair com sucesso e faz rollback se uma exceção
            for levantada dentro do bloco. Use para INSERT/UPDATE/DELETE.
        dict_row: Se True, usa `RealDictCursor`, fazendo o cursor retornar cada
            linha como dicionário em vez de tupla.

    Yields:
        psycopg2.extensions.cursor: Cursor pronto para executar comandos SQL.
    """
    conn = get_connection()
    kw = {"cursor_factory": RealDictCursor} if dict_row else {}
    cursor = conn.cursor(**kw)
    try:
        yield cursor
        if write:
            conn.commit()
    except Exception:
        if write:
            conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def init_db():
    """Cria as tabelas do esquema caso ainda não existam.

    Operação idempotente: todas as tabelas (`usuarios`, `arquivos`, `sessoes`,
    `pacientes`, `paciente_arquivos` e `relatorios`) são criadas via
    `CREATE TABLE IF NOT EXISTS`, podendo ser chamada com segurança a cada
    inicialização da aplicação.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id               SERIAL       PRIMARY KEY,
            nome             VARCHAR(255) NOT NULL,
            email            VARCHAR(255) UNIQUE NOT NULL,
            cpf              VARCHAR(14)  UNIQUE NOT NULL,
            senha            VARCHAR(255) NOT NULL,
            profissao        VARCHAR(100) NOT NULL,
            telefone         VARCHAR(20),
            data_nascimento  DATE,
            bio              TEXT,
            foto_perfil      BYTEA,
            foto_nome        VARCHAR(255),
            foto_tipo        VARCHAR(50),
            criado_em        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS arquivos (
            id             SERIAL   PRIMARY KEY,
            usuario_id     INTEGER  NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            nome           VARCHAR(255) NOT NULL,
            descricao      TEXT         DEFAULT '',
            tamanho_bytes  INTEGER  NOT NULL,
            num_linhas     INTEGER,
            encoding       VARCHAR(50),
            conteudo       BYTEA    NOT NULL,
            criado_em      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessoes (
            id         SERIAL      PRIMARY KEY,
            token      VARCHAR(36) UNIQUE NOT NULL,
            usuario_id INTEGER     NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            criado_em  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
            expira_em  TIMESTAMP   NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pacientes (
            id              SERIAL       PRIMARY KEY,
            usuario_id      INTEGER      NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            nome            VARCHAR(255) NOT NULL,
            sexo            VARCHAR(20),
            data_nascimento DATE,
            email           VARCHAR(255),
            telefone        VARCHAR(20),
            altura          NUMERIC(5,2),
            peso            NUMERIC(5,2),
            nota            TEXT,
            criado_em       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            atualizado_em   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paciente_arquivos (
            paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
            arquivo_id  INTEGER NOT NULL REFERENCES arquivos(id)  ON DELETE CASCADE,
            PRIMARY KEY (paciente_id, arquivo_id),
            UNIQUE (arquivo_id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relatorios (
            id             SERIAL       PRIMARY KEY,
            usuario_id     INTEGER      NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            nome           VARCHAR(255) NOT NULL,
            arquivo_origem VARCHAR(255),
            tamanho_bytes  INTEGER      NOT NULL,
            conteudo       BYTEA        NOT NULL,
            criado_em      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
