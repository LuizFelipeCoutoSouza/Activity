"""
model/database.py — Conexão com o banco de dados e inicialização do esquema.

Expõe:
  get_connection() — abre e retorna uma conexão psycopg2 com o PostgreSQL.
  db_cursor(write, dict_row) — context manager que abre cursor, commita/rollback
                               automaticamente e fecha conexão ao sair.
  init_db()        — cria as tabelas com o esquema completo (idempotente via IF NOT EXISTS).
"""

from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="Activity",
        user="postgres",
        password="postgres",
        port=5432,
    )


@contextmanager
def db_cursor(write: bool = False, dict_row: bool = False):
    """
    Context manager de cursor psycopg2.

    write=True  → commita no sucesso, rollback na exceção.
    dict_row=True → cursor com RealDictCursor (retorna dicts).
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

    conn.commit()
    cursor.close()
    conn.close()
