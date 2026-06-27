# -----------------------------------------------------------------------------
# Activity — Sistema web para análise de dados de actigrafia
#
# Monografia apresentada à Escola de Artes, Ciências e Humanidades da
# Universidade de São Paulo, como parte dos requisitos exigidos na disciplina
# ACH2017 — Projeto Supervisionado ou de Graduação I, para obtenção do título
# de Bacharelado em Sistemas de Informação.
#
# Modalidade: TCC curto (1 semestre) — em grupo
#
# Autores:
#   Laila Malafaia Vieira
#   Luiz Felipe Couto de Souza
#
# Orientadora: Profa. Dra. Ana Amélia Benedito Silva
#
# São Paulo, 2026
# -----------------------------------------------------------------------------

"""Página de gerenciamento de pacientes.

CRUD completo de pacientes com listagem paginada e busca por nome/e-mail.
Cadastro e edição ocorrem em um diálogo com abas (dados e arquivos vinculados),
respeitando a regra "um arquivo pertence a no máximo um paciente".
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from controller.arquivo_controller import ArquivoController
from controller.paciente_controller import PacienteController
from view.ui import set_toast, render_toast, fmt_telefone, get_usuario_id, paginacao

SEXO_OPCOES = ["Masculino", "Feminino", "Outro", "Não informado"]
POR_PAGINA  = 8


# ── Entrada principal ─────────────────────────────────────────────────────────

def registro_de_pacientes_page():
    """Renderiza a página de registro de pacientes.

    Aplica o guard de autenticação, exibe métricas-resumo (pacientes e arquivos
    atribuídos/sem paciente), abre o diálogo de cadastro/edição quando sinalizado
    no estado da sessão e mostra a listagem com busca e paginação.
    """
    st.title("👥 Registro de pacientes")

    usuario_id = get_usuario_id()
    if not usuario_id:
        return

    render_toast()

    if "novo_paciente" in st.session_state:
        _dialogo_paciente(None, usuario_id)
    elif "editando_paciente_id" in st.session_state:
        _dialogo_paciente(st.session_state["editando_paciente_id"], usuario_id)

    pacientes = PacienteController.listar(usuario_id)
    arquivos  = ArquivoController.listar(usuario_id)

    arquivos_atribuidos     = sum(int(p.get("num_arquivos", 0)) for p in pacientes)
    arquivos_nao_atribuidos = len(arquivos) - arquivos_atribuidos

    col1, col2, col3 = st.columns(3)
    col1.metric("Pacientes", len(pacientes))
    col2.metric("Arquivos atribuídos", arquivos_atribuidos)
    col3.metric("Arquivos sem paciente", arquivos_nao_atribuidos)

    # ── Cabeçalho + botão novo ────────────────────────────────────────────────
    col_titulo, col_btn = st.columns([5, 1])
    col_titulo.subheader("Pacientes")
    if col_btn.button("➕ Novo", type="primary", width="stretch", key="btn_novo_pac"):
        st.session_state["novo_paciente"] = True
        st.rerun()

    st.divider()

    if not pacientes:
        st.info("Nenhum paciente cadastrado ainda. Clique em **➕ Novo** para começar.")
        return

    # ── Busca ─────────────────────────────────────────────────────────────────
    busca = st.text_input(
        "Buscar",
        placeholder="Nome ou e-mail...",
        label_visibility="collapsed",
        key="busca_paciente",
    )
    if busca:
        termo     = busca.lower()
        pacientes = [
            p for p in pacientes
            if termo in p["nome"].lower() or termo in (p.get("email") or "").lower()
        ]

    if not pacientes:
        st.info("Nenhum paciente corresponde à busca.")
        return

    # ── Paginação ─────────────────────────────────────────────────────────────
    n_paginas = max(1, (len(pacientes) + POR_PAGINA - 1) // POR_PAGINA)
    pagina    = min(max(st.session_state.get("pag_pacientes", 0), 0), n_paginas - 1)
    st.session_state["pag_pacientes"] = pagina
    inicio    = pagina * POR_PAGINA
    pag_atual = pacientes[inicio : inicio + POR_PAGINA]

    # ── Cabeçalho da tabela ───────────────────────────────────────────────────
    cols_h = st.columns([3, 1.5, 0.8, 2.5, 1.5, 0.8, 2])
    for col, h in zip(cols_h, ["Nome", "Sexo", "Idade", "E-mail", "Telefone", "Arquivos", "Ações"]):
        col.markdown(f"**{h}**")

    for p in pag_atual:
        _linha_paciente(p, usuario_id)

    paginacao(pagina, n_paginas, "pag_pacientes")


# ── Dialog de cadastro / edição ───────────────────────────────────────────────

@st.dialog("Paciente", width="large")
def _dialogo_paciente(paciente_id: int | None, usuario_id: int):
    """Exibe o diálogo de cadastro ou edição de paciente, com duas abas.

    A aba **Dados** edita os campos do paciente; a aba **Arquivos vinculados**
    (apenas em edição) sincroniza os vínculos via multiselect. Opera em modo de
    criação quando `paciente_id` é None.

    Args:
        paciente_id: Id do paciente a editar, ou None para cadastrar um novo.
        usuario_id: Id do usuário dono.
    """
    is_novo = paciente_id is None
    st.subheader("Novo paciente" if is_novo else "Editar paciente")

    dados = {} if is_novo else (PacienteController.buscar(paciente_id, usuario_id) or {})

    tab_dados, tab_arquivos = st.tabs(["📋  Dados", "📁  Arquivos vinculados"])

    # ── Aba Dados ─────────────────────────────────────────────────────────────
    with tab_dados:
        nome = st.text_input("Nome *", value=dados.get("nome", ""), placeholder="Nome completo")

        col1, col2 = st.columns(2)
        with col1:
            sexo_atual = dados.get("sexo") or ""
            sexo_idx   = SEXO_OPCOES.index(sexo_atual) if sexo_atual in SEXO_OPCOES else None
            sexo = st.selectbox(
                "Sexo", SEXO_OPCOES,
                index=sexo_idx, placeholder="Selecione...",
            )
            email = st.text_input(
                "E-mail", value=dados.get("email") or "",
                placeholder="paciente@email.com",
            )
            altura = st.number_input(
                "Altura (cm)",
                min_value=0.0, max_value=300.0, step=0.5, format="%.1f",
                value=float(dados["altura"]) if dados.get("altura") else None,
                placeholder="Ex: 170.0",
            )

        with col2:
            data_nasc = st.date_input(
                "Data de nascimento",
                value=dados.get("data_nascimento"),
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                format="DD/MM/YYYY",
            )
            telefone = st.text_input(
                "Telefone", value=dados.get("telefone") or "",
                max_chars=15, placeholder="(00) 00000-0000",
            )
            peso = st.number_input(
                "Peso (kg)",
                min_value=0.0, max_value=500.0, step=0.5, format="%.1f",
                value=float(dados["peso"]) if dados.get("peso") else None,
                placeholder="Ex: 70.0",
            )

        nota = st.text_area(
            "Nota", value=dados.get("nota") or "",
            placeholder="Observações clínicas...", height=80, max_chars=1000,
        )

        st.divider()
        c1, c2 = st.columns(2)

        if c1.button("Salvar", type="primary", width="stretch", key="btn_salvar_pac"):
            if is_novo:
                ok, msg, _ = PacienteController.cadastrar(
                    usuario_id, nome, sexo, data_nasc,
                    email, telefone, altura, peso, nota,
                )
                if ok:
                    st.session_state.pop("novo_paciente", None)
                    set_toast(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                ok, msg = PacienteController.atualizar(
                    paciente_id, usuario_id, nome, sexo, data_nasc,
                    email, telefone, altura, peso, nota,
                )
                if ok:
                    st.session_state.pop("editando_paciente_id", None)
                    set_toast(msg)
                    st.rerun()
                else:
                    st.error(msg)

        if c2.button("Cancelar", width="stretch", key="btn_cancelar_pac"):
            st.session_state.pop("novo_paciente", None)
            st.session_state.pop("editando_paciente_id", None)
            st.rerun()

    # ── Aba Arquivos ──────────────────────────────────────────────────────────
    with tab_arquivos:
        if is_novo:
            st.info("Salve os dados do paciente primeiro para vincular arquivos.")
        else:
            disponiveis, _ = PacienteController.arquivos_disponiveis(usuario_id, paciente_id)
            vinculados = PacienteController.listar_arquivos(paciente_id)
            ids_vin    = {a["arquivo_id"] for a in vinculados}

            if not disponiveis:
                st.info("Nenhum arquivo disponível. Faça upload em **Conjunto de dados**.")
            else:
                mapa    = {a["nome"]: a["id"] for a in disponiveis}
                default = [a["nome"] for a in disponiveis if a["id"] in ids_vin]

                selecao = st.multiselect(
                    "Arquivos deste paciente",
                    options=list(mapa.keys()),
                    default=default,
                )

                if st.button(
                    "Salvar vínculos", type="primary",
                    width="stretch", key="btn_salvar_vin",
                ):
                    novos_ids = [mapa[n] for n in selecao]
                    ok, msg   = PacienteController.sincronizar_arquivos(paciente_id, novos_ids)
                    if ok:
                        set_toast(msg)
                        st.rerun()
                    else:
                        st.error(msg)


# ── Linha de paciente ─────────────────────────────────────────────────────────

def _linha_paciente(p: dict, usuario_id: int):
    """Renderiza uma linha da tabela de pacientes, com ações de editar/excluir.

    A exclusão usa confirmação inline controlada por `confirm_del_pac` no estado
    da sessão.

    Args:
        p: Dicionário de dados do paciente.
        usuario_id: Id do usuário dono.
    """
    st.divider()
    cols = st.columns([3, 1.5, 0.8, 2.5, 1.5, 0.8, 2])

    cols[0].write(f"**{p['nome']}**")
    cols[1].write(p.get("sexo") or "—")
    cols[2].write(str(_idade(p.get("data_nascimento"))) if p.get("data_nascimento") else "—")
    cols[3].write(p.get("email") or "—")
    cols[4].write(fmt_telefone(p["telefone"]) if p.get("telefone") else "—")
    cols[5].write(str(int(p.get("num_arquivos", 0))))

    with cols[6]:
        c1, c2 = st.columns(2)
        if c1.button("Editar", key=f"ed_pac_{p['id']}", width="stretch"):
            st.session_state["editando_paciente_id"] = p["id"]
            st.rerun()

        if st.session_state.get("confirm_del_pac") != p["id"]:
            if c2.button("Excluir", key=f"del_pac_{p['id']}", width="stretch"):
                st.session_state["confirm_del_pac"] = p["id"]
                st.rerun()

    if st.session_state.get("confirm_del_pac") == p["id"]:
        st.warning(f"Excluir **{p['nome']}**? Os arquivos vinculados serão desvinculados, mas não apagados.")
        cd1, cd2 = st.columns(2)
        if cd1.button("✓ Confirmar", key=f"conf_del_pac_{p['id']}", type="primary"):
            ok, msg = PacienteController.deletar(p["id"], usuario_id)
            st.session_state.pop("confirm_del_pac", None)
            set_toast(msg) if ok else st.error(msg)
            st.rerun()
        if cd2.button("✗ Cancelar", key=f"canc_del_pac_{p['id']}"):
            st.session_state.pop("confirm_del_pac", None)
            st.rerun()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _idade(data_nascimento) -> int | None:
    """Calcula a idade em anos completos a partir de uma data de nascimento.

    Args:
        data_nascimento: Objeto `date` de nascimento, ou valor falsy.

    Returns:
        int | None: Idade em anos, ou None se a data não for informada.
    """
    if not data_nascimento:
        return None
    hoje = date.today()
    anos = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        anos -= 1
    return anos


