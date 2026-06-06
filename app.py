"""
app.py — Ponto de entrada da aplicação Activity.

Responsabilidades:
  - Inicializar o banco de dados (init_db).
  - Processar operações pendentes de cookie (set / delete).
  - Restaurar sessão a partir de cookie persistido entre refreshes.
  - Detectar autenticação por e-mail ou Google OAuth.
  - Normalizar os dados do usuário em st.session_state["usuario"].
  - Rotear para as áreas públicas (login, cadastro) ou protegidas (home).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from model.database import init_db

st.set_page_config(page_title="Activity", initial_sidebar_state="expanded", layout="wide")

init_db()

_COOKIE = "activity_session"


# ── Helpers de cookie ─────────────────────────────────────────────────────────

def _gravar_cookie(token: str, dias: int) -> None:
    """
    Grava o cookie de sessão via JS no iframe same-origin.
    dias=0 → session cookie (apagado ao fechar o browser).
    dias>0 → cookie persistente com max-age em segundos.
    """
    if dias > 0:
        js = (f'window.parent.document.cookie="'
              f'{_COOKIE}={token};max-age={dias * 86400};path=/;SameSite=Strict";')
    else:
        js = f'window.parent.document.cookie="{_COOKIE}={token};path=/;SameSite=Strict";'
    st.iframe(f"<script>{js}</script>", height=1)


def _apagar_cookie() -> None:
    """Remove o cookie de sessão via JS (expiração no passado)."""
    js = (f'window.parent.document.cookie="'
          f'{_COOKIE}=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/;";')
    st.iframe(f"<script>{js}</script>", height=1)


# ── Operações pendentes de cookie (agendadas por login / logout) ───────────────
# Executadas antes de qualquer lógica de autenticação para que o cookie
# esteja disponível no próximo refresh.

if "_set_cookie" in st.session_state:
    info = st.session_state.pop("_set_cookie")
    _gravar_cookie(info["token"], info["dias"])

if st.session_state.pop("_delete_cookie", False):
    _apagar_cookie()


# ── Detecção de autenticação ──────────────────────────────────────────────────

google_logado = st.user.is_logged_in
email_logado  = st.session_state.get("logado", False)

# Normaliza dados do usuário Google na sessão (executa uma vez após o callback OAuth)
if google_logado and "usuario" not in st.session_state:
    st.session_state["usuario"] = {
        "nome":      st.user.name,
        "email":     st.user.email,
        "tipo_auth": "google",
    }

# ── Restauração de sessão por cookie ─────────────────────────────────────────
# Lê o token do cookie HTTP (disponível desde o primeiro render via st.context).
# Válido apenas para login por e-mail — Google usa o próprio mecanismo OAuth.

if not email_logado and not google_logado:
    _token = st.context.cookies.get(_COOKIE)
    if _token:
        from controller.user_controller import UserController
        _dados = UserController.restaurar_sessao(_token)
        if _dados:
            st.session_state["usuario"]        = _dados
            st.session_state["logado"]         = True
            st.session_state["_session_token"] = _token
            st.session_state.setdefault("pagina", "home")
            email_logado = True

if "pagina" not in st.session_state:
    st.session_state["pagina"] = "login"

pagina      = st.session_state["pagina"]
autenticado = google_logado or email_logado

# ── Rotas públicas (sem login) ────────────────────────────────────────────────

if not autenticado:
    if pagina == "cadastro":
        from view.cadastro import cadastro_page
        cadastro_page()
    else:
        from view.login import login_page
        login_page()
    st.stop()

# ── Rotas protegidas (requerem login) ─────────────────────────────────────────

if pagina in ("login", "home"):
    from view.home import home_page
    home_page()
elif pagina == "cadastro":
    from view.cadastro import cadastro_page
    cadastro_page()