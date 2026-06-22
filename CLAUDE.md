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

# Ou rodar tudo (app + PostgreSQL) via Docker Compose
docker compose up --build
```

A conexão com o banco lê variáveis de ambiente com defaults locais (`DB_HOST=localhost`, `DB_PORT=5432`, `DB_NAME=Activity`, `DB_USER=postgres`, `DB_PASSWORD=postgres` — ver `get_connection()` em `model/database.py`). `init_db()` é chamado na inicialização e cria as seis tabelas com esquema completo via `CREATE TABLE IF NOT EXISTS`.

### Docker

- `Dockerfile` — imagem baseada em `continuumio/miniconda3`; cria um ambiente conda `pyActi39` (Python 3.9, exigido pelo pyActigraphy), instala `numba==0.57.1` antes do `pyActigraphy==1.2.2`, depois `requirements.txt`, e sobe o Streamlit em `0.0.0.0:8501`.
- `docker-compose.yml` — dois serviços: `db` (`postgres:16`, volume persistente `db_data`, healthcheck `pg_isready`) e `app` (build local, depende de `db` saudável, recebe `DB_HOST=db` e demais credenciais via env).

## Dependencies

Declared in `requirements.txt`. Instalar com `pip install -r requirements.txt`.

| Pacote | Versão | Uso |
|---|---|---|
| `streamlit` | 1.50.0 | Framework principal de UI |
| `psycopg2-binary` | 2.9.12 | Driver PostgreSQL; `RealDictCursor` para SELECT como dict |
| `bcrypt` | 5.0.0 | Hash de senhas em `UserModel.criar_usuario` e verificação no login |
| `streamlit-keyup` | 0.3.0 | `st_keyup` — dispara rerun a cada tecla (busca em tempo real em `conjunto_de_dados.py`) |
| `pyActigraphy` | 1.2.2 | Parsing/análise de actigrafia: `BaseRaw`, métricas IS/IV/L5/M10, máscara de inatividade — `construir_raw`/`construir_raw_cached` em `view/ui.py`, usado por `analises.py` e `comparacao.py` |
| `pandas` | 2.1.4 | DataFrames/séries temporais — usado por `model/condor_parser.py` e pelas páginas de análise/comparação |
| `plotly` | 6.7.0 | Gráficos interativos (`graph_objects`/`express`) — `grafico_combinado_dia` em `view/ui.py` (usado por `analises.py`), gráfico próprio em `comparacao.py` e `analise_temperatura.py` |
| `kaleido` | 0.2.1 | Engine de renderização estática do plotly (`fig.to_image`) — exporta gráficos como PNG em `view/pages/analises.py` e `view/pages/analise_temperatura.py`. Pinado em 0.2.1 (versões ≥1.x exigem Chrome/Chromium instalado) |
| `pillow` | 11.3.0 | Empilha os PNGs diários em uma colagem vertical (`_gerar_colagem_graficos`) em `view/pages/analises.py` |

## File Structure

```
Activity/
├── app.py                          # Entry point: cookie ops, session restore, auth guard, routing
├── requirements.txt                # Dependências diretas com versões pinadas
├── Dockerfile                      # Imagem conda (Python 3.9) que sobe o Streamlit
├── docker-compose.yml              # Orquestra app + PostgreSQL 16
├── .dockerignore                   # Exclusões do contexto de build
├── .streamlit/
│   └── config.toml                 # Streamlit theme (light)
│
├── model/                          # Camada de dados — acesso a BD + lógica de domínio
│   ├── database.py                 # get_connection(), db_cursor(), init_db() — cria as 6 tabelas
│   ├── user_model.py               # CRUD de usuários + foto + senha
│   ├── arquivo_model.py            # CRUD de arquivos .txt (salvar, listar, buscar, deletar)
│   ├── sessao_model.py             # CRUD de sessões persistentes (criar, buscar, deletar)
│   ├── paciente_model.py           # CRUD de pacientes + vínculo com arquivos
│   ├── relatorio_model.py          # CRUD de relatórios exportados (.zip) por usuário
│   └── condor_parser.py            # Parser de arquivos Condor (actigrafia): carregar_condor,
│                                   #   dias_disponiveis, filtrar_dia, gerar_txt, gerar_csv —
│                                   #   sem acesso a BD
│
├── controller/                     # Camada de negócio — validação + orquestração
│   ├── user_controller.py          # cadastrar, login, atualizar_perfil, atualizar_foto,
│   │                               #   atualizar_senha, listar, deletar,
│   │                               #   buscar_perfil, buscar_perfil_por_email,
│   │                               #   iniciar_sessao, encerrar_sessao, restaurar_sessao
│   ├── arquivo_controller.py       # fazer_upload, listar, baixar, atualizar_metadados,
│   │                               #   substituir_arquivo, deletar, gerar_zip,
│   │                               #   carregar_actigrafia, dias_disponiveis, filtrar_dia,
│   │                               #   exportar_dados
│   ├── paciente_controller.py      # cadastrar, listar, buscar, atualizar, deletar,
│   │                               #   listar_arquivos, arquivos_disponiveis, sincronizar_arquivos
│   └── relatorio_controller.py     # salvar, listar, baixar, deletar relatórios exportados
│
└── view/                           # Camada de apresentação — UI Streamlit
    ├── ui.py                       # Utilitários compartilhados (ver seção "view/ui.py")
    ├── login.py                    # login_page()
    ├── cadastro.py                 # cadastro_page()
    ├── home.py                     # home_page(): navbar, sidebar, roteamento lazy
    └── pages/                      # Uma página por arquivo; importadas lazily por home.py
        ├── analises.py             # analises_page()              [em desenvolvimento]
        ├── analise_temperatura.py  # analise_temperatura_page()   [implementado]
        ├── comparacao.py           # comparacao_page()            [implementado]
        ├── conjunto_de_dados.py    # conjunto_de_dados_page()      [implementado]
        ├── registro_de_pacientes.py# registro_de_pacientes_page()  [implementado]
        ├── exportar_relatorio.py   # exportar_relatorio_page()     [implementado]
        └── configuracoes.py        # configuracoes_page()          [implementado]
```

## Architecture

MVC estrito. **A view nunca importa da camada model diretamente.** O fluxo de dados desce em uma única direção:

```
view → controller → model
```

Qualquer acesso a banco de dados, parsing de arquivos ou lógica de sessão deve passar pelo controller correspondente. Violações desse padrão devem ser corrigidas imediatamente.

**`app.py`** — única fonte de verdade de autenticação. Ordem de execução em cada render:
1. `init_db()` (idempotente)
2. Processa operações pendentes de cookie (`_set_cookie` / `_delete_cookie` em session_state) via `st.components.v1.html()`
3. Detecta `email_logado`
4. Tenta restaurar sessão via `UserController.restaurar_sessao(token)` se não autenticado
5. Roteia: públicas (`login`, `cadastro`) ou protegidas (`home`)

**`model/database.py`** — única fonte de verdade de conexão. `get_connection()` retorna uma conexão psycopg2 bruta. `db_cursor(write, dict_row)` é um context manager que abre cursor, commita/faz rollback automaticamente e fecha a conexão — usado por todos os models. `init_db()` cria as seis tabelas (`usuarios`, `arquivos`, `sessoes`, `pacientes`, `paciente_arquivos`, `relatorios`) via `CREATE TABLE IF NOT EXISTS`.

**`model/user_model.py`** — operações de BD puras, sem validação. Usa `db_cursor(dict_row=True)` para SELECT. O helper `_row()` converte `RealDictRow` em `dict` e transforma colunas `BYTEA` (foto_perfil) de `memoryview` para `bytes`.

**`model/arquivo_model.py`** — operações de BD para a tabela `arquivos`. Todos os métodos filtram por `usuario_id` para garantir isolamento entre usuários. `listar` retorna `list[dict]`.

**`model/sessao_model.py`** — operações de BD para a tabela `sessoes`. Métodos: `criar(usuario_id, dias)` → token UUID; `buscar_usuario_id(token)` → int | None (valida expiração); `deletar(token)` → None.

**`model/paciente_model.py`** — operações de BD para as tabelas `pacientes` e `paciente_arquivos`. Todos os métodos de paciente filtram por `usuario_id`. Vínculo com arquivos via `vincular_arquivo` / `desvincular_arquivo` (ON CONFLICT DO NOTHING). `listar_arquivos_ocupados(usuario_id, paciente_id_atual)` retorna arquivos vinculados a outros pacientes do mesmo usuário.

**`model/condor_parser.py`** — lógica de domínio para arquivos Condor (actigrafia). Não acessa BD. Funções: `carregar_condor(path_ou_bytes)` → `(metadata, DataFrame)`; `dias_disponiveis(df)` → `list[str]`; `filtrar_dia(df, data_str)` → `DataFrame`; `gerar_txt(raw_original, df)` → `bytes` (reconstrói o .txt Condor preservando cabeçalho/campos, com os dados de `df`); `gerar_csv(df)` → `bytes` (CSV simples com os campos e valores). Consumido exclusivamente por `ArquivoController`.

**`model/relatorio_model.py`** — operações de BD para a tabela `relatorios`. Todos os métodos filtram por `usuario_id`. `salvar(usuario_id, nome, arquivo_origem, tamanho_bytes, conteudo)` → `int` (id); `listar`/`buscar`/`deletar` seguem o mesmo padrão de `arquivo_model.py`.

**`controller/user_controller.py`** — toda lógica de negócio de usuário e sessão:

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
| `buscar_perfil_por_email(email)` | Retorna perfil pelo e-mail |
| `iniciar_sessao(usuario_id, dias)` | Cria sessão persistente; retorna token UUID |
| `encerrar_sessao(token)` | Invalida sessão no banco |
| `restaurar_sessao(token)` | Valida token + recarrega perfil; retorna dict ou None |

**`controller/arquivo_controller.py`** — validação, orquestração de arquivos e análise de actigrafia:

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
| `exportar_dados(arquivo_id, usuario_id, df)` | Gera ZIP com `.txt` (formato Condor original) + `.csv` a partir de `df`; retorna `(bytes, nome)` |

**`controller/paciente_controller.py`** — validação e orquestração de pacientes e vínculos:

| Método | Descrição |
|--------|-----------|
| `cadastrar(usuario_id, nome, ...)` | Valida e cria paciente; retorna `(bool, str, int\|None)` |
| `listar(usuario_id)` | Lista pacientes com contagem de arquivos vinculados |
| `buscar(paciente_id, usuario_id)` | Retorna dict do paciente ou None |
| `atualizar(paciente_id, usuario_id, ...)` | Valida e persiste alterações; retorna `(bool, str)` |
| `deletar(paciente_id, usuario_id)` | Remove paciente (arquivos são desvinculados, não apagados) |
| `listar_arquivos(paciente_id)` | Lista arquivos vinculados ao paciente |
| `arquivos_disponiveis(usuario_id, paciente_id)` | Retorna `(disponíveis, ocupados_por_outros)` |
| `sincronizar_arquivos(paciente_id, novos_ids)` | Diff-based: vincula/desvincula para atingir `novos_ids` |

**`controller/relatorio_controller.py`** — orquestração de relatórios exportados (tabela `relatorios`):

| Método | Descrição |
|--------|-----------|
| `salvar(usuario_id, nome, arquivo_origem, conteudo)` | Salva o ZIP exportado; retorna `int` (id) |
| `listar(usuario_id)` | Lista metadados dos relatórios do usuário |
| `baixar(relatorio_id, usuario_id)` | Retorna `(bytes, nome)` do ZIP |
| `deletar(relatorio_id, usuario_id)` | Remove relatório; retorna `(bool, str)` |

**`view/ui.py`** — módulo de utilitários compartilhados (ver seção dedicada abaixo).

**`view/login.py`** — layout dois colunas. Sucesso no login: chama `UserController.iniciar_sessao()`, armazena o token em `_set_cookie` e `_session_token` no session_state, seta `logado`/`usuario`/`pagina` e chama `st.rerun()`. O cookie é gravado no browser no render seguinte por `app.py`.

**`view/cadastro.py`** — formulário de cadastro. Usa `Profissao.opcoes()` e `forca_senha()` de `view/ui.py`.

**`view/home.py`** — shell autenticado. Renderiza navbar (logo + avatar via `avatar_html()`), sidebar (botões de navegação + logout) e roteia para `view/pages/` via import lazy. Logout: chama `UserController.encerrar_sessao()`, agenda deleção do cookie (`_delete_cookie = True`) e chama `st.rerun()`.

**`view/pages/configuracoes.py`** — duas abas: **Perfil** (foto + formulário de dados) e **Segurança** (troca de senha). Usa `UserController.buscar_perfil_por_email()` para carregar dados frescos do banco. Usa `render_toast()` e `set_toast()` de `view/ui.py`.

**`view/pages/conjunto_de_dados.py`** — gerencia arquivos .txt. Abas: listagem paginada com busca (`st_keyup`), filtros com padrão draft/aplicado, seleção em massa, download (zip automático via JS), exclusão; upload com descrição individual por arquivo. Cache de conteúdo via `@st.cache_data(ttl=120)`. Download em massa delega para `ArquivoController.gerar_zip()` e dispara o browser via JS (`window.parent.document.createElement('a')`) injetado com `st.components.v1.html()`.

**`view/pages/analises.py`** — visualização de actigrafia, construída em torno do objeto `BaseRaw` do pyActigraphy (`construir_raw`/`construir_raw_cached`, de `view/ui.py`). Estrutura:
- Carrega o arquivo escolhido (cacheado via `carregar_actigrafia_cached`, de `view/ui.py`) e exibe nome, sexo e data de nascimento do sujeito a partir de `metadata` (`SUBJECT_NAME`, `SUBJECT_GENDER`, `SUBJECT_DATE_OF_BIRTH`, normalizados por `rotulo_genero`).
- **Descartar início do registro**: checkbox + `st.pills` (0h–12h, passo 2h) que recorta `df` a partir de `primeiro_registro + duração`, antes de qualquer outro cálculo — afeta métricas, faixas e dias disponíveis, não só a exibição.
- **Opções de exibição** (`st.expander`): escolha do modo de atividade (PIM/TAT/ZCM via `st.radio`, com `MODOS_ATIVIDADE` filtrado pelas colunas existentes); **mascaramento de inatividade** via `raw.create_inactivity_mask(f"{duração}h")` + `raw.mask_inactivity = True` (checkbox + `st.pills` 0h–12h, passo 2h) — propaga automaticamente para `raw.data`, afetando gráficos e métricas sem alterar `df`; checkboxes e sliders de faixa de valores (escala) para atividade, luz e temperatura.
- **Parâmetros das métricas não paramétricas** (`st.expander`): `selectbox` de frequência de reamostragem (`10min`–`2H`, padrão `1H`) e `number_input` de limiar de binarização (padrão `4`), repassados a `raw.IS()`/`raw.IV()`/`raw.L5()`/`raw.M10()` via `_metricas_ritmo(raw, freq=..., limiar=...)`.
- **Filtrar dias exibidos** (`st.expander`): filtros somente de exibição — dia da semana (`st.pills`, multi, opções `DIAS_SEMANA` de `view/ui.py`) e período do dia (`st.segmented_control`: Manhã/Tarde/Noite/Personalizado, este último com `st.slider` de intervalo de horas) — recortam os gráficos por dia (`grafico_combinado_dia`) sem alterar dados nem métricas. A numeração "Dia N" é preservada via `numero_por_dia`, calculado antes da filtragem.
- Gráficos combinados por dia via `grafico_combinado_dia` (de `view/ui.py`, Plotly `go.Figure`): atividade + eixos extras de luz/temperatura sobrepostos, sombreamento do período noturno (`sombrear_periodo_noturno`) e de marcações de evento.
- **Exportar** (ao final da página): dois checkboxes definem o conteúdo do .zip exportado — **Dados (.txt + .csv)** e **Gráficos (.png)** (desabilitado se nenhum dia estiver em `dias_exibidos`). O processamento só ocorre ao clicar em **"Baixar exportação (.zip)"** (`st.button`, dentro de `st.spinner`) — evita reprocessar a cada interação da página. "Dados": `_preparar_df_exportacao` copia `df` e zera/esvazia valores conforme a seleção atual — sinais não marcados em "Opções de exibição" e linhas fora de "Filtrar dias exibidos" saem zerados; valores fora das faixas exibidas saem zerados; períodos mascarados como inatividade saem vazios (NaN). "Gráficos": `_gerar_colagem_graficos`/`@st.cache_data(ttl=120)` renderiza o `grafico_combinado_dia` de cada dia em `dias_exibidos` como PNG via `fig.to_image()` (kaleido) e empilha as imagens verticalmente com Pillow — uma linha por dia, na mesma ordem/numeração "Dia N" exibida nos gráficos. Os itens selecionados vão para `ArquivoController.exportar_dados(..., incluir_dados, extras)`, que monta um único ZIP (`.txt`/`.csv` e/ou `_graficos.png`) via `_gerar_export_zip`/`@st.cache_data(ttl=120)`. Ao concluir: `_salvar_relatorio` salva o ZIP em `RelatorioController.salvar(usuario_id, zip_nome, nome_origem, zip_bytes)` (toda exportação baixada também fica disponível em **Exportar relatório**) e o resultado é guardado em `st.session_state["_export_pronto"]` (chaveado por `arquivo_id`) seguido de `st.rerun()`. No próximo render, o download é disparado automaticamente via JS (`window.parent.document.createElement('a')` + `.click()`, base64 do ZIP) injetado com `st.components.v1.html()` — mesmo padrão de download em massa de `conjunto_de_dados.py` — resultando em um clique único do usuário.

**`view/pages/analise_temperatura.py`** — análise de temperatura de um único arquivo. Carrega o arquivo escolhido via `carregar_actigrafia_cached` e exibe nome, sexo e idade do sujeito (`rotulo_genero`, `calcular_idade`). Para `TEMPERATURE` e/ou `EXT TEMPERATURE` (via `coluna_numerica_utilizavel`, ignorando colunas ausentes ou totalmente nulas): monta uma matriz dia × hora com a temperatura média de cada hora (`_matriz_temperatura_horaria`, com linha/coluna "Média"), renderiza um gráfico de linha com a média por hora (`_grafico_medias_horarias`) e exibe a matriz estilizada com escala de cores azul→vermelho (`_estilizar_matriz`/`_renderizar_matriz`) mais um cartão de estatísticas descritivas (`_exibir_estatisticas`: média, mediana, mín, máx, amplitude, desvio padrão, variância). **Exportar**: checkboxes para **Tabelas (.csv)** (matrizes + estatísticas) e **Gráfico (.png)**; ao clicar em **"Baixar exportação (.zip)"**, monta os extras e delega a `ArquivoController.exportar_dados(..., incluir_dados=False, extras=...)` via `_gerar_export_zip`/`@st.cache_data(ttl=120)`; salva cópia em **Exportar relatório** (`_salvar_relatorio`) e dispara o download automático no próximo render, mesmo padrão de `analises.py`.

**`view/pages/comparacao.py`** — sobrepõe gráficos de N arquivos selecionados (`st.multiselect`) em um único `go.Figure` por dia comparado, reaproveitando `grafico_combinado_dia`'s building blocks de `view/ui.py` (`sombrear_periodo_noturno`, cores, `LARGURA_EIXO_EXTRA`, `MODOS_ATIVIDADE`, `DIAS_SEMANA`). Cada arquivo recebe uma cor da `_PALETA_CORES`. **Opções de exibição**: modo de atividade comum a todos os arquivos (`st.radio`, apenas modos presentes em todas as colunas) e checkboxes/sliders de atividade, luz e temperatura com **escala compartilhada** — faixas mín/máx calculadas sobre todos os arquivos selecionados, para comparação direta de amplitude. **Alinhamento de dias** (`st.radio` "Alinhar por"): "Número do dia do registro" — compara o Dia N de cada arquivo (posição relativa dentro do próprio registro, via `st.pills` 1..max_dias); ou "Dia da semana" — compara a primeira ocorrência de cada dia da semana selecionado (`st.pills` com `DIAS_SEMANA`) entre os arquivos (ex.: sábado de um com sábado de outro). Para cada grupo resultante, `_grafico_comparacao_dia` desenha uma linha de atividade por arquivo (mais luz/temperatura como eixos extras tracejados), com `_eixo_relativo` normalizando cada dia para a data de referência `2000-01-01` (00:00–24:00) para alinhar visualmente dias de datas calendário diferentes.

**`view/pages/registro_de_pacientes.py`** — CRUD completo de pacientes com paginação (8/página) e busca por nome/e-mail. Cadastro e edição via `@st.dialog("Paciente", width="large")` com duas abas: **Dados** (campos do paciente) e **Arquivos vinculados** (multiselect dos arquivos disponíveis do usuário). Exclusão com confirmação inline. Regra de negócio: um arquivo só pode ser vinculado a um paciente — arquivos já ocupados ficam invisíveis no multiselect.

**`view/pages/exportar_relatorio.py`** — lista os relatórios (.zip) salvos por `_salvar_relatorio` em `analises.py`. Listagem paginada (8/página, `paginacao` de `view/ui.py`) com nome, arquivo de origem e tamanho; cada linha tem `download_button` (conteúdo cacheado via `@st.cache_data(ttl=120)`) e botão **Excluir** com confirmação via `@st.dialog`.

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
| `get_usuario_id()` | `→ int \| None` | Retorna o id do usuário e-mail ou None; exibe `st.info` automático — usar como guard no topo de cada página restrita |
| `paginacao(pagina, n_paginas, chave)` | `→ None` | Renderiza controles Anterior/Próxima; `chave` é a chave de `session_state` que armazena a página atual |
| `set_toast(msg, icon?)` | `→ None` | Agenda toast para o próximo render (via `st.session_state`) |
| `render_toast()` | `→ None` | Consome e exibe o toast pendente; chamar no início de cada página |
| `rotulo_genero(valor)` | `str \| None → str` | Normaliza `SUBJECT_GENDER` (`"M"`/`"F"`/...) para rótulo exibível |
| `calcular_idade(data_nascimento)` | `→ str` | Calcula idade a partir de `SUBJECT_DATE_OF_BIRTH` |
| `coluna_numerica_utilizavel(df, nome)` | `→ pd.Series \| None` | Retorna a coluna como série numérica, ou `None` se ausente/totalmente nula |
| `carregar_actigrafia_cached(arquivo_id, usuario_id)` | `@st.cache_data(ttl=120)` | Wrapper cacheado de `ArquivoController.carregar_actigrafia` |
| `construir_raw(nome, df, coluna)` / `construir_raw_cached(...)` | `→ BaseRaw` | Constrói o objeto `BaseRaw` do pyActigraphy a partir de `df`/coluna de atividade; versão cacheada via `@st.cache_data(ttl=120)` |
| `grafico_combinado_dia(dia, numero_dia, serie_atividade, ...)` | `@st.cache_data(ttl=120) → go.Figure` | Gráfico Plotly combinado de um dia: atividade + eixos extras de luz/temperatura, sombreamento noturno e de eventos |
| `sombrear_periodo_noturno(fig, inicio, row=, col=)` | `→ None` | Adiciona sombreamento do período noturno a um `go.Figure` |
| `rotulo_dia(numero_dia, dia)` | `→ str` | Rótulo "Dia N (dd/mm/aaaa)" usado nos títulos dos gráficos |
| `COR_LINHA`, `COR_LUZ`, `COR_TEMPERATURA`, `COR_LEGENDA`, `COR_SOMBRA_NOITE`, `COR_SOMBRA_EVENTO` | `str` | Cores padrão usadas nos gráficos de actigrafia |
| `MODOS_ATIVIDADE` | `list[str]` | `["PIM", "TAT", "ZCM"]` |
| `DIAS_SEMANA` | `list[str]` | `["Segunda", ..., "Domingo"]` |
| `LARGURA_EIXO_EXTRA` | `float` | Largura (fração do domínio x) reservada a cada eixo y extra (luz/temperatura) |

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

Login por e-mail; `app.py` detecta via `st.session_state["logado"] == True`.

`st.session_state["usuario"]` contém todos os campos do perfil retornados por `UserModel.buscar_por_id()`, incluindo `foto_perfil` (bytes ou None). Novas páginas devem ler apenas esse dict.

### Persistência de sessão entre refreshes

`st.session_state` é volátil — zerado em cada refresh de página. Para o login por e-mail, a sessão é persistida via cookie HTTP + tabela `sessoes` no banco:

| Evento | O que acontece |
|--------|----------------|
| Login | `UserController.iniciar_sessao()` grava token UUID → `_set_cookie` agendado em session_state |
| Próximo render | `app.py` detecta `_set_cookie` → injeta JS via `st.components.v1.html()` que escreve o cookie |
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

## Navigation

**Nível 1 — `app.py`**: `st.session_state["pagina"]` → `"login"` | `"cadastro"` | `"home"`.

**Nível 2 — `home.py`**: `st.session_state["pagina_atual"]` → `"Análises"` | `"Análise de temperatura"` | `"Comparação"` | `"Conjunto de dados"` | `"Registro de pacientes"` | `"Exportar relatório"` | `"Configurações"`.

Para adicionar uma nova página autenticada:
1. Criar `view/pages/minha_pagina.py` com `minha_pagina_page()`.
2. Adicionar `elif` em `_conteudo()` em `home.py`.
3. Adicionar botão correspondente em `_sidebar()` em `home.py`.

## Database

Conexão em `model/database.py` via `get_connection()`, configurável por variáveis de ambiente (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) com defaults locais (`localhost:5432`, database `Activity`, user/password `postgres`). No Docker Compose, o serviço `app` recebe `DB_HOST=db`.

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

### Tabela `pacientes`

| Coluna          | Tipo          | Constraint                                   |
|-----------------|---------------|----------------------------------------------|
| id              | SERIAL        | PRIMARY KEY                                  |
| usuario_id      | INTEGER       | NOT NULL, FK → usuarios(id) ON DELETE CASCADE |
| nome            | VARCHAR(255)  | NOT NULL                                     |
| sexo            | VARCHAR(20)   | nullable                                     |
| data_nascimento | DATE          | nullable                                     |
| email           | VARCHAR(255)  | nullable                                     |
| telefone        | VARCHAR(20)   | nullable                                     |
| altura          | NUMERIC(5,2)  | nullable                                     |
| peso            | NUMERIC(5,2)  | nullable                                     |
| nota            | TEXT          | nullable                                     |
| criado_em       | TIMESTAMP     | DEFAULT CURRENT_TIMESTAMP                    |
| atualizado_em   | TIMESTAMP     | DEFAULT CURRENT_TIMESTAMP                    |

### Tabela `paciente_arquivos`

| Coluna      | Tipo    | Constraint                                    |
|-------------|---------|-----------------------------------------------|
| paciente_id | INTEGER | NOT NULL, FK → pacientes(id) ON DELETE CASCADE |
| arquivo_id  | INTEGER | NOT NULL, FK → arquivos(id) ON DELETE CASCADE  |
| —           | —       | PRIMARY KEY (paciente_id, arquivo_id)          |
| —           | —       | UNIQUE (arquivo_id) — 1 arquivo → 1 paciente  |

### Tabela `relatorios`

| Coluna         | Tipo         | Constraint                                  |
|----------------|--------------|----------------------------------------------|
| id             | SERIAL       | PRIMARY KEY                                 |
| usuario_id     | INTEGER      | NOT NULL, FK → usuarios(id) ON DELETE CASCADE |
| nome           | VARCHAR(255) | NOT NULL (nome do .zip exportado)           |
| arquivo_origem | VARCHAR(255) | nullable (nome do arquivo .txt de origem)   |
| tamanho_bytes  | INTEGER      | NOT NULL                                    |
| conteudo       | BYTEA        | NOT NULL                                    |
| criado_em      | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP                   |

As seis tabelas são criadas com esquema completo em `init_db()` via `CREATE TABLE IF NOT EXISTS`.
