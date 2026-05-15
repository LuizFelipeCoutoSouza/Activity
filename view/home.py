import streamlit as st

PAGINAS = [
    ("📊", "Análises"),
    ("🗃️", "Conjunto de dados"),
    ("👥", "Registro de pacientes"),
    ("📄", "Exportar relatório"),
]

def home_page():
    _estilos()

    usuario   = st.session_state.get("usuario", {})
    tipo_auth = usuario.get("tipo_auth", "email")

    _navbar(usuario)
    _sidebar(tipo_auth)
    _conteudo()


# ── Navbar ────────────────────────────────────────────────────────────────────

def _navbar(usuario):
    tipo_auth = usuario.get("tipo_auth", "email")
    nome      = usuario.get("nome", "Usuário")
    avatar    = _avatar_html(usuario, tipo_auth)

    st.markdown(f"""
    <div class="navbar">
        <div class="navbar-brand">
            <span class="navbar-logo">A</span>
            Activity
        </div>
        <div class="navbar-user" title="{nome}">
            {avatar}
        </div>
    </div>
    """, unsafe_allow_html=True)


def _avatar_html(usuario, tipo_auth):
    picture = None
    if tipo_auth == "google" and st.user.is_logged_in:
        picture = getattr(st.user, "picture", None)

    if picture:
        return f'<img class="avatar-img" src="{picture}" alt="avatar">'

    inicial = usuario.get("nome", "U")[0].upper()
    return f'<div class="avatar-placeholder">{inicial}</div>'


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _sidebar(tipo_auth):
    pagina_atual = st.session_state.get("pagina_atual", "Análises")

    with st.sidebar:
        st.markdown("## Activity")
        st.divider()

        for icone, nome in PAGINAS:
            ativo = pagina_atual == nome
            if st.button(
                f"{icone}  {nome}",
                use_container_width=True,
                type="primary" if ativo else "secondary",
                key=f"nav_{nome}",
            ):
                st.session_state["pagina_atual"] = nome
                st.rerun()

        st.divider()

        if st.button("⚙️  Configurações", use_container_width=True, key="nav_config"):
            st.session_state["pagina_atual"] = "Configurações"
            st.rerun()

        if st.button("🚪  Sair", use_container_width=True, key="nav_logout"):
            _logout(tipo_auth)


# ── Conteúdo principal ────────────────────────────────────────────────────────

def _conteudo():
    pagina = st.session_state.get("pagina_atual", "Análises")

    if pagina == "Análises":
        from view.pages.analises import analises_page
        analises_page()
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

def _logout(tipo_auth):
    for chave in ("logado", "usuario", "pagina_atual"):
        st.session_state.pop(chave, None)
    st.session_state["pagina"] = "login"

    if tipo_auth == "google":
        st.logout()
    else:
        st.rerun()


# ── Estilos ───────────────────────────────────────────────────────────────────

def _estilos():
    st.markdown("""
    <style>
    /* Remove o header padrão do Streamlit */
    header[data-testid="stHeader"] { display: none; }

    /* Navbar */
    .navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 1.5rem;
        background: #ffffff;
        border-bottom: 1px solid #e8e8e8;
        margin: -4rem -4rem 1.5rem -4rem;
    }
    .navbar-brand {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        font-size: 1.2rem;
        font-weight: 700;
        color: #0f1117;
    }
    .navbar-logo {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 8px;
        background: #0068C9;
        color: white;
        font-weight: 800;
        font-size: 1rem;
    }
    .navbar-user { display: flex; align-items: center; }

    /* Avatar */
    .avatar-img {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        object-fit: cover;
        border: 2px solid #e0e0e0;
    }
    .avatar-placeholder {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #0068C9;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)