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

The app expects a local PostgreSQL instance (`localhost:5432`, database `Activity`, user `postgres`, password `postgres`). `init_db()` is called at startup and cria as três tabelas com esquema completo via `CREATE TABLE IF NOT EXISTS`.

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
├── app.py                          # Entry point: cookie ops, session restore, auth guard, routing
├── requirements.txt                # Dependências diretas com versões pinadas
├── .streamlit/
│   ├── config.toml                 # Streamlit theme (light)
│   └── secrets.toml                # Google OAuth credentials — NÃO COMMITAR
│
├── model/                          # Camada de dados — acesso a BD + lógica de domínio
│   ├── database.py                 # get_connection(), init_db() — cria as 3 tabelas
│   ├── UserModel.py                # CRUD de usuários + foto + senha
│   ├── ArquivoModel.py             # CRUD de arquivos .txt (salvar, listar, buscar, deletar)
│   ├── SessaoModel.py              # CRUD de sessões persistentes (criar, buscar, deletar)
│   └── condor_parser.py            # Parser de arquivos Condor (actigrafia): carregar_condor,
│                                   #   dias_disponiveis, filtrar_dia — sem acesso a BD
│
├── controller/                     # Camada de negócio — validação + orquestração
│   ├── UserController.py           # cadastrar, login, atualizar_perfil, atualizar_foto,
│   │                               #   atualizar_senha, listar, deletar,
│   │                               #   buscar_perfil, buscar_perfil_por_email,
│   │                               #   iniciar_sessao, encerrar_sessao, restaurar_sessao
│   └── ArquivoController.py        # fazer_upload, listar, baixar, atualizar_metadados,
│                                   #   substituir_arquivo, deletar, gerar_zip,
│                                   #   carregar_actigrafia, dias_disponiveis, filtrar_dia
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

MVC estrito. **A view nunca importa da camada model diretamente.** O fluxo de dados desce em uma única direção:

```
view → controller → model
```

Qualquer acesso a banco de dados, parsing de arquivos ou lógica de sessão deve passar pelo controller correspondente. Violações desse padrão devem ser corrigidas imediatamente.

**`app.py`** — única fonte de verdade de autenticação. Ordem de execução em cada render:
1. `init_db()` (idempotente)
2. Processa operações pendentes de cookie (`_set_cookie` / `_delete_cookie` em session_state) via `streamlit.components.v1.html()`
3. Detecta `google_logado` e `email_logado`
4. Tenta restaurar sessão via `UserController.restaurar_sessao(token)` se não autenticado
5. Roteia: públicas (`login`, `cadastro`) ou protegidas (`home`)

**`model/database.py`** — única fonte de verdade de conexão. `get_connection()` retorna uma conexão psycopg2 bruta. Cada método do model abre e fecha sua própria conexão (sem pool). `init_db()` cria as três tabelas (`usuarios`, `arquivos`, `sessoes`) via `CREATE TABLE IF NOT EXISTS`.

**`model/UserModel.py`** — operações de BD puras, sem validação. Usa `RealDictCursor` para SELECT. O helper `_row()` converte `RealDictRow` em `dict` e transforma colunas `BYTEA` (foto_perfil) de `memoryview` para `bytes`.

**`model/ArquivoModel.py`** — operações de BD para a tabela `arquivos`. Todos os métodos filtram por `usuario_id` para garantir isolamento entre usuários.

**`model/SessaoModel.py`** — operações de BD para a tabela `sessoes`. Métodos: `criar(usuario_id, dias)` → token UUID; `buscar_usuario_id(token)` → int | None (valida expiração); `deletar(token)` → None.

**`model/condor_parser.py`** — lógica de domínio para arquivos Condor (actigrafia). Não acessa BD. Funções: `carregar_condor(path_ou_bytes)` → `(metadata, DataFrame)`; `dias_disponiveis(df)` → `list[str]`; `filtrar_dia(df, data_str)` → `DataFrame`. Consumido exclusivamente por `ArquivoController`.

**`controller/UserController.py`** — toda lógica de negócio de usuário e sessão:

| Método | Descrição |
|--------|-----------|
| `cadastrar(...)` | Valida e cria usuário |
| `login(email, senha)` | Autentica por e-mail; retorna `(bool, str, dict)` |
| `atualizar_perfil(...)` | Valida e persiste alterações de perfil |
| `atualizar_foto(...)` | Salva bytes de foto no banco |
| `atualizar_senha(...)` | Valida senha atual e persiste nova hash |
| `listar()` | Lista todos os usuários |
| `deletar(user_id)` | Remove usuário |
| `buscar_perfil(usuario_id)` | Retorna perfil completo pelo id |
| `buscar_perfil_por_email(email)` | Retorna perfil pelo e-mail (contas Google) |
| `iniciar_sessao(usuario_id, dias)` | Cria sessão persistente; retorna token UUID |
| `encerrar_sessao(token)` | Invalida sessão no banco |
| `restaurar_sessao(token)` | Valida token + recarrega perfil; retorna dict ou None |

**`controller/ArquivoController.py`** — validação, orquestração de arquivos e análise de actigrafia:

| Método | Descrição |
|--------|-----------|
| `fazer_upload(usuario_id, file, desc)` | Valida e salva arquivo .txt |
| `listar(usuario_id)` | Lista metadados dos arquivos do usuário |
| `baixar(arquivo_id, usuario_id)` | Retorna `(bytes, nome)` do arquivo |
| `atualizar_metadados(...)` | Atualiza nome e descrição |
| `substituir_arquivo(...)` | Substitui conteúdo mantendo metadados |
| `deletar(arquivo_id, usuario_id)` | Remove arquivo |
| `gerar_zip(ids, usuario_id)` | Compacta múltiplos arquivos; retorna `(bytes, nome, n)` |
| `carregar_actigrafia(arquivo_id, usuario_id)` | Baixa e processa Condor; retorna `(metadata, DataFrame)` |
| `dias_disponiveis(df)` | Lista datas únicas do DataFrame Condor |
| `filtrar_dia(df, data_str)` | Filtra DataFrame para um único dia |

**`view/ui.py`** — módulo de utilitários compartilhados (ver seção dedicada abaixo).

**`view/login.py`** — layout dois colunas. Sucesso no login: chama `UserController.iniciar_sessao()`, armazena o token em `_set_cookie` e `_session_token` no session_state, seta `logado`/`usuario`/`pagina` e chama `st.rerun()`. O cookie é gravado no browser no render seguinte por `app.py`.

**`view/cadastro.py`** — formulário de cadastro. Usa `Profissao.opcoes()` e `forca_senha()` de `view/ui.py`.

**`view/home.py`** — shell autenticado. Renderiza navbar (logo + avatar via `avatar_html()`), sidebar (botões de navegação + logout) e roteia para `view/pages/` via import lazy. Logout e-mail: chama `UserController.encerrar_sessao()`, agenda deleção do cookie (`_delete_cookie = True`) e chama `st.rerun()`. Logout Google: `st.logout()`.

**`view/pages/configuracoes.py`** — duas abas: **Perfil** (foto + formulário de dados) e **Segurança** (troca de senha). Aba Segurança desabilitada para contas Google. Usa `UserController.buscar_perfil_por_email()` para carregar dados frescos do banco. Usa `render_toast()` e `set_toast()` de `view/ui.py`.

**`view/pages/conjunto_de_dados.py`** — gerencia arquivos .txt. Abas: listagem paginada com busca (`st_keyup`), filtros com padrão draft/aplicado, seleção em massa, download (zip automático via JS), exclusão; upload com descrição individual por arquivo. Cache de conteúdo via `@st.cache_data(ttl=120)`. Download em massa delega para `ArquivoController.gerar_zip()` e dispara o browser via JS (`window.parent.document.createElement('a')`).

**`view/pages/analises.py`** — visualização de actigrafia. Seleciona arquivo (do banco via `ArquivoController.listar`) e dia; carrega e processa via `ArquivoController.carregar_actigrafia` (cacheado em `_carregar_actigrafia` no nível de módulo com `@st.cache_data(ttl=120)`). Exibe métricas (PIM, temperatura) e gráficos (PIM, temperatura, luz, melanopic EDI).

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

`st.session_state["usuario"]` para usuários e-mail contém todos os campos do perfil retornados por `UserModel.buscar_por_id()`, incluindo `foto_perfil` (bytes ou None). Novas páginas devem ler apenas esse dict, nunca `st.user` diretamente.

Credenciais OAuth em `.streamlit/secrets.toml` — **não commitar**.

### Persistência de sessão entre refreshes (login por e-mail)

`st.session_state` é volátil — zerado em cada refresh de página. Para o login por e-mail, a sessão é persistida via cookie HTTP + tabela `sessoes` no banco:

| Evento | O que acontece |
|--------|----------------|
| Login | `UserController.iniciar_sessao()` grava token UUID → `_set_cookie` agendado em session_state |
| Próximo render | `app.py` detecta `_set_cookie` → injeta JS via `components.html()` que escreve o cookie |
| Refresh (F5) | `st.context.cookies` lê o token → `UserController.restaurar_sessao()` valida + recarrega perfil |
| Logout | `UserController.encerrar_sessao()` remove token do banco → `_delete_cookie` agendado → JS apaga o cookie |

**"Manter conectado por 30 dias"** (checkbox na tela de login):
- Marcado (`dias=30`) → cookie com `max-age=30 dias` + sessão no banco com 30 dias
- Desmarcado (`dias=0`) → session cookie (some ao fechar o browser) + sessão no banco com 2 horas

**Chaves reservadas de session_state para o mecanismo de sessão:**

| Chave | Tipo | Descrição |
|-------|------|-----------|
| `_session_token` | `str` | Token UUID da sessão ativa; usado pelo logout para deletar do banco |
| `_set_cookie` | `dict` | `{"token": str, "dias": int}` — agendado por login, consumido por `app.py` |
| `_delete_cookie` | `bool` | `True` — agendado por logout, consumido por `app.py` |

O Google OAuth não usa este mecanismo — a persistência é gerenciada pelo próprio Streamlit.

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

### Tabela `sessoes`

| Coluna     | Tipo         | Constraint                                  |
|------------|--------------|---------------------------------------------|
| id         | SERIAL       | PRIMARY KEY                                 |
| token      | VARCHAR(36)  | UNIQUE, NOT NULL (UUID v4)                  |
| usuario_id | INTEGER      | NOT NULL, FK → usuarios(id) ON DELETE CASCADE |
| criado_em  | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP                   |
| expira_em  | TIMESTAMP    | NOT NULL                                    |

As três tabelas são criadas com esquema completo em `init_db()` via `CREATE TABLE IF NOT EXISTS`. Para adicionar colunas em bancos já existentes, executar o `ALTER TABLE` manualmente ou recriar o banco.