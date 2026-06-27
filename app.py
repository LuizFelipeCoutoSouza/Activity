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

"""Ponto de entrada da aplicação Activity e única fonte de verdade de autenticação.

A cada render, o script inicializa o banco (`init_db`), aplica operações pendentes
de cookie (gravar/apagar), tenta restaurar a sessão a partir do cookie persistido,
detecta a autenticação e roteia para as áreas públicas (`login`, `cadastro`) ou
protegidas (`home`).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import streamlit.components.v1 as components
from model.database import init_db

st.set_page_config(page_title="Activity", initial_sidebar_state="expanded", layout="wide")

init_db()

_COOKIE = "activity_session"


# ── Helpers de cookie ─────────────────────────────────────────────────────────

def _gravar_cookie(token: str, dias: int) -> None:
    """Grava o cookie de sessão via JS, a partir do iframe same-origin.

    Args:
        token: Token UUID da sessão a guardar no cookie.
        dias: Validade em dias. Se 0, grava um session cookie (apagado ao fechar
            o navegador); se maior que 0, grava um cookie persistente com
            `max-age` correspondente.
    """
    if dias > 0:
        js = (f'window.parent.document.cookie="'
              f'{_COOKIE}={token};max-age={dias * 86400};path=/;SameSite=Strict";')
    else:
        js = f'window.parent.document.cookie="{_COOKIE}={token};path=/;SameSite=Strict";'
    components.html(f"<script>{js}</script>", height=0)


def _apagar_cookie() -> None:
    """Remove o cookie de sessão via JS (expiração no passado)."""
    js = (f'window.parent.document.cookie="'
          f'{_COOKIE}=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/;";')
    components.html(f"<script>{js}</script>", height=0)


# ── Operações pendentes de cookie (agendadas por login / logout) ───────────────
# Executadas antes de qualquer lógica de autenticação para que o cookie
# esteja disponível no próximo refresh.

if "_set_cookie" in st.session_state:
    info = st.session_state.pop("_set_cookie")
    _gravar_cookie(info["token"], info["dias"])

if st.session_state.pop("_delete_cookie", False):
    _apagar_cookie()


# ── Detecção de autenticação ──────────────────────────────────────────────────

email_logado = st.session_state.get("logado", False)

# ── Restauração de sessão por cookie ─────────────────────────────────────────
# Lê o token do cookie HTTP (disponível desde o primeiro render via st.context).

if not email_logado:
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
autenticado = email_logado

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