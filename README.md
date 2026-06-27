<div align="center">

<img src="imagens/Logo_EACH-USP.png" alt="EACH-USP" height="90">

# Activity

**Sistema web para análise de dados de actigrafia**

</div>

---

Monografia apresentada à Escola de Artes, Ciências e Humanidades da Universidade de São Paulo, como parte dos requisitos exigidos na disciplina **ACH2017 — Projeto Supervisionado ou de Graduação I**, para obtenção do título de Bacharelado em Sistemas de Informação.

- **Modalidade:** TCC curto (1 semestre) — em grupo
- **Autores:** Laila Malafaia Vieira · Luiz Felipe Couto de Souza
- **Orientadora:** Profa. Dra. Ana Amélia Benedito Silva
- **São Paulo, 2026**

---

## Sobre o projeto

**Activity** é uma aplicação web construída em [Streamlit](https://streamlit.io/) para a organização, filtragem e visualização de dados de **actigrafia**. Destina-se a profissionais de saúde — médicos, enfermeiros, fisioterapeutas e pesquisadores — que precisam analisar registros de atividade, luz e temperatura coletados por actígrafos.

A aplicação importa arquivos no formato **Condor**, calcula métricas não paramétricas de ritmo circadiano (IS, IV, L5, M10) por meio da biblioteca [pyActigraphy](https://github.com/ghammad/pyActigraphy), e oferece gráficos interativos, comparação entre registros, análise de temperatura, gestão de pacientes e exportação de relatórios.

## Funcionalidades

- **Conjunto de dados** — upload, listagem paginada com busca em tempo real, filtros, seleção em massa, download (`.zip`) e exclusão de arquivos `.txt`.
- **Análises** — visualização de actigrafia por dia (atividade + luz + temperatura), descarte do início do registro, mascaramento de inatividade, escolha do modo de atividade (PIM/TAT/ZCM), métricas não paramétricas configuráveis e filtros de exibição por dia da semana e período.
- **Análise de temperatura** — matriz dia × hora com temperatura média, gráfico de médias horárias e estatísticas descritivas.
- **Comparação** — sobreposição de múltiplos arquivos em um mesmo gráfico, com escala compartilhada e alinhamento por número do dia ou por dia da semana.
- **Registro de pacientes** — CRUD completo de pacientes com vínculo de arquivos (um arquivo por paciente).
- **Exportar relatório** — exportação de dados (`.txt`/`.csv`) e gráficos (`.png`) em `.zip`, com histórico de relatórios salvos.
- **Autenticação** — cadastro e login por e-mail, com sessão persistente entre refreshes (cookie + banco) e opção "manter conectado por 30 dias".

## Arquitetura

O projeto segue um padrão **MVC estrito**, com fluxo de dados em uma única direção:

```
view → controller → model
```

A camada `view` **nunca** importa da camada `model` diretamente — todo acesso a banco de dados, parsing de arquivos e lógica de sessão passa pelo `controller` correspondente.

```
Activity/
├── app.py              # Entry point: cookies, restauração de sessão, autenticação, roteamento
├── model/              # Acesso ao banco + lógica de domínio (database, usuários, arquivos,
│                       #   sessões, pacientes, relatórios, parser Condor)
├── controller/         # Validação + orquestração (usuário, arquivo, paciente, relatório)
└── view/               # UI Streamlit
    ├── ui.py           # Utilitários compartilhados
    ├── login.py / cadastro.py / home.py
    └── pages/          # Uma página por arquivo (importadas lazily por home.py)
```

## Tecnologias

| Pacote | Versão | Uso |
|---|---|---|
| `streamlit` | 1.50.0 | Framework principal de UI |
| `psycopg2-binary` | 2.9.12 | Driver PostgreSQL |
| `bcrypt` | 5.0.0 | Hash de senhas |
| `streamlit-keyup` | 0.3.0 | Busca em tempo real |
| `pyActigraphy` | 1.2.2 | Parsing/análise de actigrafia e métricas IS/IV/L5/M10 |
| `pandas` | 2.1.4 | DataFrames e séries temporais |
| `plotly` | 6.7.0 | Gráficos interativos |
| `kaleido` | 0.2.1 | Exportação de gráficos como PNG |
| `pillow` | 11.3.0 | Colagem dos gráficos diários |

Banco de dados: **PostgreSQL 16**.

## Pré-requisitos

- Python **3.9** (exigido pelo pyActigraphy)
- PostgreSQL 16 em execução, ou Docker + Docker Compose

## Como executar

### Localmente

```bash
# Ative o ambiente virtual
source .venv/bin/activate

# Instale as dependências
pip install -r requirements.txt

# Execute a aplicação
streamlit run app.py
```

A aplicação ficará disponível em `http://localhost:8501`.

### Com Docker Compose

Sobe a aplicação e o banco PostgreSQL de uma só vez:

```bash
docker compose up --build
```

- **`db`** — `postgres:16`, com volume persistente `db_data` e healthcheck `pg_isready`.
- **`app`** — build local (imagem conda com ambiente `pyActi39`, Python 3.9), que depende do banco saudável e recebe `DB_HOST=db`.

## Configuração do banco

A conexão lê variáveis de ambiente com defaults locais (ver `get_connection()` em `model/database.py`):

| Variável | Default |
|---|---|
| `DB_HOST` | `localhost` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `Activity` |
| `DB_USER` | `postgres` |
| `DB_PASSWORD` | `postgres` |

Na inicialização, `init_db()` cria automaticamente as seis tabelas (`usuarios`, `arquivos`, `sessoes`, `pacientes`, `paciente_arquivos`, `relatorios`) via `CREATE TABLE IF NOT EXISTS` — não é necessário executar migrações manualmente.

## Licença

Projeto acadêmico desenvolvido como Trabalho de Conclusão de Curso (TCC) no Bacharelado em Sistemas de Informação da EACH-USP.
