# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Activity** is a Streamlit web app for analyzing actigraphy data, developed as a TCC (undergraduate thesis) at EACH-USP. It serves health professionals (médicos, enfermeiros, fisioterapeutas, pesquisadores) who need to organize, filter, and visualize actigraphy data.

## Commands

```bash
# Install dependencies (activate venv first)
source .venv/bin/activate
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

The app expects a local PostgreSQL instance (`localhost:5432`, database `Activity`, user `postgres`, password `postgres`). `init_db()` is called at startup, creates tables and runs idempotent `ALTER TABLE` migrations.

## Dependencies

Declared in `requirements.txt`. Instalar com `pip install -r requirements.txt`.

| Pacote | Versão | Uso |
|---|---|---|
| `streamlit` | 1.57.0 | Framework principal de UI |
| `psycopg2-binary` | 2.9.12 | Driver PostgreSQL; `RealDictCursor` para SELECT como dict |
| `bcrypt` | 5.0.0 | Hash de senhas em `UserModel.criar_usuario` e verificação no login |
| `streamlit-keyup` | 0.3.0 | `st_keyup` — dispara rerun a cada tecla (busca em tempo real em `conjunto_de_dados.py`) |

## File Structure

```
Activity/
├── app.py                          # Entry point: auth guard, DB init, page routing
├── requirements.txt                # Dependências diretas com versões pinadas
├── .streamlit/
│   ├── config.toml                 # Streamlit theme (light)
│   └── secrets.toml                # Google OAuth credentials — NÃO COMMITAR
│
├── model/                          # Camada de dados — acesso direto ao PostgreSQL
│   ├── database.py                 # get_connection(), init_db() — migrações idempotentes
│   ├── UserModel.py                # CRUD de usuários + foto + senha
│   └── ArquivoModel.py             # CRUD de arquivos .txt (salvar, listar, buscar, deletar)
│
├── controller/                     # Camada de negócio — validação + orquestração
│   ├── UserController.py           # cadastrar, login, atualizar_perfil, atualizar_foto,
│   │                               #   atualizar_senha, listar, deletar
│   └── ArquivoController.py        # fazer_upload, listar, baixar, atualizar_metadados,
│                                   #   substituir_arquivo, deletar
│
└── view/                           # Camada de apresentação — UI Streamlit
    ├── ui.py                       # Utilitários compartilhados (ver seção "view/ui.py")
    ├── login.py                    # login_page()
    ├── cadastro.py                 # cadastro_page()
    ├── home.py                     # home_page(): navbar, sidebar, roteamento lazy
    └── pages/                      # Uma página por arquivo; importadas lazily por home.py
        ├── analises.py             # analises_page()          [em desenvolvimento]
        ├── conjunto_de_dados.py    # conjunto_de_dados_page() [implementado]
        ├── registro_de_pacientes.py# registro_de_pacientes_page() [em desenvolvimento]
        ├── exportar_relatorio.py   # exportar_relatorio_page() [em desenvolvimento]
        └── configuracoes.py        # configuracoes_page()     [implementado]
```

## Architecture

MVC estrito. O fluxo de dados desce em uma única direção: `view → controller → model`.

**`app.py`** — única fonte de verdade de autenticação. Executa `init_db()`, detecta `google_logado` (`st.user.is_logged_in`) e `email_logado` (`st.session_state["logado"]`), combinando em `autenticado`. No primeiro render pós-callback Google, normaliza `st.user.name/email` em `st.session_state["usuario"]`. Rotas públicas: `login`, `cadastro`; todo o resto exige `autenticado`.

**`model/database.py`** — única fonte de verdade de conexão. `get_connection()` retorna uma conexão psycopg2 bruta. Cada método do model abre e fecha sua própria conexão (sem pool). `init_db()` cria as tabelas e executa as migrações de colunas novas via `ADD COLUMN IF NOT EXISTS`.

**`model/UserModel.py`** — operações de BD puras, sem validação. Usa `RealDictCursor` para SELECT. O helper `_row()` converte `RealDictRow` em `dict` e transforma colunas `BYTEA` (foto_perfil) de `memoryview` para `bytes`.

**`model/ArquivoModel.py`** — operações de BD para a tabela `arquivos`. Todos os métodos filtram por `usuario_id` para garantir isolamento entre usuários.

**`controller/UserController.py`** — toda validação de usuário fica aqui (campos obrigatórios, força de senha, CPF via `re.sub(r"\D","")`, duplicatas). Retorna `(bool, str)` ou `(bool, str, dict)`.

**`controller/ArquivoController.py`** — validação e orquestração de arquivos. Detecta encoding automático (`utf-8-sig`, `utf-8`, `latin-1`, `cp1252`). Retorna `(bool, str)`.

**`view/ui.py`** — módulo de utilitários compartilhados (ver seção dedicada abaixo).

**`view/login.py`** — layout dois colunas. Coluna esquerda: descrição do app. Coluna direita: form e-mail/senha + botão Google (`st.login()`). Sucesso: seta `st.session_state["logado"]`, `["usuario"]`, `["pagina"]` e chama `st.rerun()`.

**`view/cadastro.py`** — formulário de cadastro. Usa `Profissao.opcoes()` e `forca_senha()` de `view/ui.py`.

**`view/home.py`** — shell autenticado. Renderiza navbar (logo + avatar via `avatar_html()`), sidebar (botões de navegação + logout) e roteia para `view/pages/` via import lazy. Logout: `st.logout()` para Google; limpa session_state + `st.rerun()` para e-mail.

**`view/pages/configuracoes.py`** — duas abas: **Perfil** (foto + formulário de dados) e **Segurança** (troca de senha). Aba Segurança desabilitada para contas Google. Usa `render_toast()` e `set_toast()` de `view/ui.py`.

**`view/pages/conjunto_de_dados.py`** — gerencia arquivos .txt. Abas: listagem paginada com busca (`st_keyup`), seleção em massa, download (zip), exclusão; upload com descrição individual por arquivo. Cache de conteúdo via `@st.cache_data(ttl=120)`.

## view/ui.py — Utilitários compartilhados

Qualquer código de UI reutilizável pertence aqui. Não duplicar em páginas individuais.

| Exportação | Tipo | Descrição |
|---|---|---|
| `Profissao` | `str, Enum` | Profissões válidas; `.opcoes()` retorna `list[str]` para selectbox |
| `AVATAR_NAV` | `int = 36` | Tamanho de avatar na navbar (px) |
| `AVATAR_SM` | `int = 80` | Tamanho de avatar no cabeçalho de perfil (px) |
| `AVATAR_LG` | `int = 120` | Tamanho de avatar na seção de foto (px) |
| `fmt_cpf(cpf)` | `str → str` | Formata para `000.000.000-00`; aceita entrada com ou sem máscara |
| `fmt_telefone(tel)` | `str → str` | Formata para `(00) 00000-0000` ou `(00) 0000-0000` |
| `forca_senha(senha)` | `str → (int, str, str)` | Retorna `(score 0-4, label, emoji)` |
| `img_b64_tag(bytes, tipo, px, caption?)` | `→ str` | HTML `<img>` circular base64 com dimensões fixas |
| `avatar_html(nome, foto, tipo, px)` | `→ str` | Avatar circular: foto ou div com inicial; funciona inline e em bloco |
| `set_toast(msg, icon?)` | `→ None` | Agenda toast para o próximo render (via `st.session_state`) |
| `render_toast()` | `→ None` | Consome e exibe o toast pendente; chamar no início de cada página |

**Padrão de toast cross-rerun:**
```python
# ao salvar:
set_toast("Salvo com sucesso.")
st.rerun()

# no início da função de página:
render_toast()
```

**Profissao enum** — herda de `str`, então `Profissao.MEDICO == "Médico"` é `True`. Usar `.opcoes()` em selectboxes e comparações diretas com valores do banco.

## Authentication

Dois métodos coexistem; `app.py` combina antes de rotear:

| Método | Detectar | `st.session_state["usuario"]` |
|--------|----------|-------------------------------|
| E-mail | `st.session_state["logado"] == True` | dict completo do banco (inclui `id`, `cpf`, `foto_perfil`, etc.) |
| Google OAuth | `st.user.is_logged_in` | `{"nome", "email", "tipo_auth": "google"}` (sem `id` se usuário não estiver no banco) |

`st.session_state["usuario"]` para usuários e-mail contém todos os campos do perfil retornados por `buscar_por_email()`, incluindo `foto_perfil` (bytes ou None). Novas páginas devem ler apenas esse dict, nunca `st.user` diretamente.

Credenciais OAuth em `.streamlit/secrets.toml` — **não commitar**.

## Navigation

**Nível 1 — `app.py`**: `st.session_state["pagina"]` → `"login"` | `"cadastro"` | `"home"`.

**Nível 2 — `home.py`**: `st.session_state["pagina_atual"]` → `"Análises"` | `"Conjunto de dados"` | `"Registro de pacientes"` | `"Exportar relatório"` | `"Configurações"`.

Para adicionar uma nova página autenticada:
1. Criar `view/pages/minha_pagina.py` com `minha_pagina_page()`.
2. Adicionar `elif` em `_conteudo()` em `home.py`.
3. Adicionar botão correspondente em `_sidebar()` em `home.py`.

## Database

Conexão hardcoded em `model/database.py` (`localhost:5432`, database `Activity`, user/password `postgres`).

### Tabela `usuarios`

| Coluna           | Tipo           | Constraint              |
|------------------|----------------|-------------------------|
| id               | SERIAL         | PRIMARY KEY             |
| nome             | VARCHAR(255)   | NOT NULL                |
| email            | VARCHAR(255)   | UNIQUE, NOT NULL        |
| cpf              | VARCHAR(14)    | UNIQUE, NOT NULL        |
| senha            | VARCHAR(255)   | NOT NULL (bcrypt)       |
| profissao        | VARCHAR(100)   | NOT NULL                |
| telefone         | VARCHAR(20)    | nullable                |
| data_nascimento  | DATE           | nullable                |
| bio              | TEXT           | nullable                |
| foto_perfil      | BYTEA          | nullable                |
| foto_nome        | VARCHAR(255)   | nullable                |
| foto_tipo        | VARCHAR(50)    | nullable (MIME type)    |
| criado_em        | TIMESTAMP      | DEFAULT CURRENT_TIMESTAMP |

### Tabela `arquivos`

| Coluna        | Tipo         | Constraint                                  |
|---------------|--------------|---------------------------------------------|
| id            | SERIAL       | PRIMARY KEY                                 |
| usuario_id    | INTEGER      | NOT NULL, FK → usuarios(id) ON DELETE CASCADE |
| nome          | VARCHAR(255) | NOT NULL                                    |
| descricao     | TEXT         | DEFAULT ''                                  |
| tamanho_bytes | INTEGER      | NOT NULL                                    |
| num_linhas    | INTEGER      | nullable                                    |
| encoding      | VARCHAR(50)  | nullable                                    |
| conteudo      | BYTEA        | NOT NULL                                    |
| criado_em     | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP                   |
| atualizado_em | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP                   |

Novas colunas são adicionadas via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` em `init_db()` — as migrações são idempotentes.
