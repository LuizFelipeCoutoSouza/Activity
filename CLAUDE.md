# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Activity** is a Streamlit web app for analyzing actigraphy data, developed as a TCC (undergraduate thesis) at EACH-USP. It serves health professionals (médicos, enfermeiros, fisioterapeutas, pesquisadores) who need to organize, filter, and visualize actigraphy data.

## Commands

```bash
# Install dependencies (activate venv first)
source .venv/bin/activate
pip install psycopg2-binary bcrypt streamlit

# Run the app
streamlit run app.py
```

The app expects a local PostgreSQL instance (`localhost:5432`, database `Activity`, user `postgres`, password `postgres`). `init_db()` is called at startup and creates the `usuarios` table if it doesn't exist.

## File Structure

```
Activity/
├── app.py                        # Entry point: auth guard, DB init, page routing
├── dependencias.txt              # pip install command for project dependencies
├── .streamlit/
│   ├── config.toml               # Streamlit theme config (light theme)
│   └── secrets.toml              # Google OAuth credentials (client_id, client_secret, etc.)
│
├── model/                        # Data layer — direct PostgreSQL access
│   ├── __init__.py
│   ├── database.py               # get_connection() and init_db() (creates 'usuarios' table)
│   └── UserModel.py              # Static CRUD: criar_usuario, listar_usuarios, buscar_por_id,
│                                 #   buscar_por_email, atualizar_usuario, deletar_usuario
│
├── controller/                   # Business logic layer — validation + orchestration
│   ├── __init__.py
│   └── UserController.py         # Static methods: cadastrar, login, listar, atualizar, deletar
│                                 #   Returns (bool, message) or (bool, message, dict)
│
└── view/                         # Presentation layer — Streamlit UI pages
    ├── __init__.py
    ├── login.py                  # login_page(): e-mail/senha + botão Google OAuth
    ├── cadastro.py               # cadastro_page(): registration form with profession selectbox
    ├── home.py                   # home_page(): shell autenticado — navbar, sidebar e roteamento
    └── pages/                    # Uma página por arquivo; importadas lazily por home.py
        ├── analises.py           # analises_page()
        ├── conjunto_de_dados.py  # conjunto_de_dados_page()
        ├── registro_de_pacientes.py  # registro_de_pacientes_page()
        ├── exportar_relatorio.py # exportar_relatorio_page()
        └── configuracoes.py      # configuracoes_page()
```

## Architecture

The project follows MVC with three packages. Data flows strictly downward: `view → controller → model`.

**`app.py`** — bootstraps the app and é a única fonte de verdade de autenticação. Executa `init_db()`, avalia `google_logado` (`st.user.is_logged_in`) e `email_logado` (`st.session_state["logado"]`), e combina os dois em `autenticado`. Se o usuário veio do callback OAuth do Google, normaliza `st.user.name/email` em `st.session_state["usuario"]`. Rotas públicas (`login`, `cadastro`) são acessíveis sem autenticação; as demais são bloqueadas com `st.stop()`.

**`model/database.py`** — single source of truth for DB connection. `get_connection()` returns a raw `psycopg2` connection. Every `UserModel` method opens and closes its own connection per call (no connection pooling).

**`model/UserModel.py`** — pure DB operations, no validation. Uses `RealDictCursor` for `SELECT` queries so rows are returned as dicts. Passwords are hashed here with `bcrypt` before insertion.

**`controller/UserController.py`** — all validation lives here (required fields, password match, length, CPF length, duplicate email/CPF). Calls `UserModel` methods and wraps results in `(bool, message)` tuples. `login()` additionally returns the user dict as a third element.

**`view/login.py`** — two-column layout. Left column: app description. Right column: login form (e-mail/senha) + botão "Google Auth" que chama `st.login()`. On e-mail login success, seta `st.session_state["logado"] = True`, `st.session_state["pagina"] = "home"` e chama `st.rerun()`. O retorno do OAuth Google é tratado inteiramente em `app.py`.

**`view/cadastro.py`** — registration form. Profession is a `st.selectbox` with fixed options: Médico, Enfermeiro, Fisioterapeuta, Pesquisador, Admin.

**`view/home.py`** — shell autenticado. Não contém conteúdo de página; apenas renderiza navbar (logo + avatar do usuário), sidebar (links de navegação, configurações, logout) e roteia para o arquivo correto em `view/pages/` via import lazy baseado em `st.session_state["pagina_atual"]`. O logout chama `st.logout()` para sessões Google ou limpa `st.session_state` e chama `st.rerun()` para sessões por e-mail.

**`view/pages/`** — cada arquivo é uma página autenticada independente com uma única função pública (`*_page()`). Para adicionar uma nova página: criar o arquivo em `view/pages/`, adicionar um `elif` em `_conteudo()` em `home.py`, e adicionar o botão correspondente em `_sidebar()` em `home.py`.

## Authentication

Dois métodos coexistem; `app.py` combina os dois antes de rotear qualquer página:

| Método | Como detectar | Dados disponíveis |
|--------|--------------|-------------------|
| E-mail | `st.session_state["logado"] == True` | `st.session_state["usuario"]` (dict do banco) |
| Google OAuth | `st.user.is_logged_in` | `st.user.name`, `st.user.email` (normalizados em `st.session_state["usuario"]` no primeiro render pós-callback) |

`st.session_state["usuario"]` sempre contém `{"nome", "email", "tipo_auth"}`, independente do método. Novas páginas devem ler apenas esse dict, nunca `st.user` diretamente.

Credenciais OAuth ficam em `.streamlit/secrets.toml` (não commitar).

## Navigation

Há dois níveis de roteamento:

**Nível 1 — `app.py`** controla qual área o usuário acessa via `st.session_state["pagina"]` (valores: `"login"`, `"cadastro"`, `"home"`). Rotas públicas são `login` e `cadastro`; todo o resto exige autenticação.

**Nível 2 — `home.py`** controla qual página autenticada é exibida via `st.session_state["pagina_atual"]` (valores: `"Análises"`, `"Conjunto de dados"`, `"Registro de pacientes"`, `"Exportar relatório"`, `"Configurações"`). A sidebar altera esse valor e chama `st.rerun()`.

Para adicionar uma nova página autenticada:
1. Criar `view/pages/minha_pagina.py` com `minha_pagina_page()`.
2. Adicionar um `elif` em `_conteudo()` em `home.py`.
3. Adicionar o botão correspondente em `_sidebar()` em `home.py`.

## Database

Connection hardcoded in `model/database.py` (`localhost:5432`, database `Activity`, user/password `postgres`). The `usuarios` table schema:

| Column      | Type           | Constraint         |
|-------------|----------------|--------------------|
| id          | SERIAL         | PRIMARY KEY        |
| nome        | VARCHAR(255)   | NOT NULL           |
| email       | VARCHAR(255)   | UNIQUE, NOT NULL   |
| cpf         | VARCHAR(14)    | UNIQUE, NOT NULL   |
| senha       | VARCHAR(255)   | NOT NULL (bcrypt)  |
| profissao   | VARCHAR(100)   | NOT NULL           |
| criado_em   | TIMESTAMP      | DEFAULT NOW()      |
