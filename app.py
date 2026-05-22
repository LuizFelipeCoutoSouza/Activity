import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from model.database import init_db

st.set_page_config(page_title="Activity", initial_sidebar_state="expanded", layout="wide")

init_db()

# --- Verificação de autenticação (email ou Google) ---
google_logado = st.user.is_logged_in
email_logado  = st.session_state.get("logado", False)
autenticado   = google_logado or email_logado

# Normaliza dados do usuário Google na sessão (executa uma vez após o callback OAuth)
if google_logado and "usuario" not in st.session_state:
    st.session_state["usuario"] = {
        "nome":      st.user.name,
        "email":     st.user.email,
        "tipo_auth": "google",
    }

if "pagina" not in st.session_state:
    st.session_state["pagina"] = "login"

pagina = st.session_state["pagina"]

# --- Rotas públicas (sem login) ---
if not autenticado:
    if pagina == "cadastro":
        from view.cadastro import cadastro_page
        cadastro_page()
    else:
        from view.login import login_page
        login_page()
    st.stop()

# --- Rotas protegidas (requerem login) ---
if pagina in ("login", "home"):
    from view.home import home_page
    home_page()
elif pagina == "cadastro":
    from view.cadastro import cadastro_page
    cadastro_page()