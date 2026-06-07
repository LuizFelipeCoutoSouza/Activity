"""
view/home.py — Shell autenticado: navbar, sidebar e roteamento entre páginas.
"""

import streamlit as st
from controller.user_controller import UserController
from view.ui import avatar_html, AVATAR_NAV

PAGINAS = [
    ("📊", "Análises"),
    ("🧪", "Análise 2"),
    ("🗃️", "Conjunto de dados"),
    ("👥", "Registro de pacientes"),
    ("📄", "Exportar relatório"),
]


def home_page():
    usuario   = st.session_state.get("usuario", {})
    tipo_auth = usuario.get("tipo_auth", "email")

    _navbar(usuario)
    _sidebar(tipo_auth)
    _conteudo()


# ── Navbar ────────────────────────────────────────────────────────────────────

def _navbar(usuario: dict):
    nome      = usuario.get("nome", "Usuário")
    foto      = usuario.get("foto_perfil")
    foto_tipo = usuario.get("foto_tipo")

    col_brand, col_user = st.columns([5, 2])
    col_brand.markdown("**Activity**")
    col_user.markdown(
        f'{avatar_html(nome, foto, foto_tipo, AVATAR_NAV)} '
        f'<strong style="vertical-align:middle;">{nome}</strong>',
        unsafe_allow_html=True,
    )
    st.divider()


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _sidebar(tipo_auth: str):
    pagina_atual = st.session_state.get("pagina_atual", "Análises")

    with st.sidebar:
        st.markdown("## Activity")
        st.divider()

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

        if st.button("⚙️  Configurações", width="stretch", key="nav_config"):
            st.session_state["pagina_atual"] = "Configurações"
            st.rerun()

        if st.button("🚪  Sair", width="stretch", key="nav_logout"):
            _logout(tipo_auth)


# ── Roteamento de conteúdo ────────────────────────────────────────────────────

def _conteudo():
    pagina = st.session_state.get("pagina_atual", "Análises")

    if pagina == "Análises":
        from view.pages.analises import analises_page
        analises_page()
    elif pagina == "Análise 2":
        from view.pages.analises2 import analises2_page
        analises2_page()
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

def _logout(tipo_auth: str):
    if tipo_auth == "email":
        token = st.session_state.pop("_session_token", None)
        if token:
            UserController.encerrar_sessao(token)
        st.session_state["_delete_cookie"] = True

    for chave in ("logado", "usuario", "pagina_atual"):
        st.session_state.pop(chave, None)
    st.session_state["pagina"] = "login"

    if tipo_auth == "google":
        st.logout()
    else:
        st.rerun()