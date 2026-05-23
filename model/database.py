"""
model/database.py — Conexão com o banco de dados e inicialização do esquema.

Expõe:
  get_connection() — abre e retorna uma conexão psycopg2 com o PostgreSQL.
  init_db()        — cria as tabelas com o esquema completo (idempotente via IF NOT EXISTS).
"""

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

    conn.commit()
    cursor.close()
    conn.close()
