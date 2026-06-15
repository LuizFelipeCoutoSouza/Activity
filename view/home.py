"""
view/home.py — Shell autenticado: navbar, sidebar e roteamento entre páginas.
"""

import base64

import streamlit as st
from controller.user_controller import UserController
from view.ui import avatar_html, AVATAR_NAV

PAGINAS = [
    ("📊", "Análises"),
    ("🌡️", "Análise de temperatura"),
    ("📈", "Comparação"),
    ("🗃️", "Conjunto de dados"),
    ("👥", "Registro de pacientes"),
    ("📄", "Exportar relatório"),
]


def home_page():
    usuario = st.session_state.get("usuario", {})

    _navbar(usuario)
    _sidebar()
    _conteudo()


# ── Navbar ────────────────────────────────────────────────────────────────────

def _navbar(usuario: dict):
    nome      = usuario.get("nome", "Usuário")
    foto      = usuario.get("foto_perfil")
    foto_tipo = usuario.get("foto_tipo")

    col_brand, col_user = st.columns([5, 2])
    col_user.markdown(
        f'{avatar_html(nome, foto, foto_tipo, AVATAR_NAV)} '
        f'<strong style="vertical-align:middle;">{nome}</strong>',
        unsafe_allow_html=True,
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _sidebar():
    pagina_atual = st.session_state.get("pagina_atual", "Análises")

    with st.sidebar:
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] > div:first-child {
            height: 100%;
            display: flex;
            flex-direction: column;
        }
        [data-testid="stSidebarContent"] {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        [data-testid="stSidebarUserContent"] {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        [data-testid="stSidebarUserContent"] > div:first-child {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > div:nth-last-child(3) {
            margin-top: auto;
        }
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
            background-color: #1a3a5c;
            border-color: #1a3a5c;
        }
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
            background-color: #142d4a;
            border-color: #142d4a;
        }
        </style>
        """, unsafe_allow_html=True)

        col_logo, col_titulo = st.columns([1, 10], vertical_alignment="center")
        col_logo.image("imagens/spring.png", width=900)
        col_titulo.markdown(
            "<div style='padding-left:0.1rem; display:flex; flex-direction:column; justify-content:center; height:100%; margin-top:-1.3rem'>"
            "<h1 style='margin:0; font-size:2.8rem; font-weight:700'>Activity</h1>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div style='margin-top:6rem'></div>", unsafe_allow_html=True)

        for icone, nome in PAGINAS:
            ativo = pagina_atual == nome
            if st.button(
                f"{icone}  {nome}",
                width="stretch",
                type="primary" if ativo else "secondary",
                key=f"nav_{nome}",
            ):
                st.session_state["pagina_atual"] = nome
                st.rerun()

        st.divider()

        if st.button(
            "⚙️  Configurações", width="stretch", key="nav_config",
            type="primary" if pagina_atual == "Configurações" else "secondary",
        ):
            st.session_state["pagina_atual"] = "Configurações"
            st.rerun()

        if st.button("🚪  Sair", width="stretch", key="nav_logout"):
            _logout()


# ── Roteamento de conteúdo ────────────────────────────────────────────────────

def _conteudo():
    pagina = st.session_state.get("pagina_atual", "Análises")

    if pagina == "Análises":
        from view.pages.analises import analises_page
        analises_page()
    elif pagina == "Análise de temperatura":
        from view.pages.analise_temperatura import analise_temperatura_page
        analise_temperatura_page()
    elif pagina == "Comparação":
        from view.pages.comparacao import comparacao_page
        comparacao_page()
    elif pagina == "Conjunto de dados":
        from view.pages.conjunto_de_dados import conjunto_de_dados_page
        conjunto_de_dados_page()
    elif pagina == "Registro de pacientes":
        from view.pages.registro_de_pacientes import registro_de_pacientes_page
        registro_de_pacientes_page()
    elif pagina == "Exportar relatório":
        from view.pages.exportar_relatorio import exportar_relatorio_page
        exportar_relatorio_page()
    elif pagina == "Configurações":
        from view.pages.configuracoes import configuracoes_page
        configuracoes_page()


# ── Logout ────────────────────────────────────────────────────────────────────

def _logout():
    token = st.session_state.pop("_session_token", None)
    if token:
        UserController.encerrar_sessao(token)
    st.session_state["_delete_cookie"] = True

    for chave in ("logado", "usuario", "pagina_atual"):
        st.session_state.pop(chave, None)
    st.session_state["pagina"] = "login"

    st.rerun()