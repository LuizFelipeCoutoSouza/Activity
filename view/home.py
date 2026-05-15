import streamlit as st

def home_page():
    usuario    = st.session_state.get("usuario", {})
    nome       = usuario.get("nome", "Usuário")
    tipo_auth  = usuario.get("tipo_auth", "email")

    st.header(f"Bem-vindo, {nome}!")

    if tipo_auth == "google":
        st.caption(f"Logado via Google · {usuario.get('email', '')}")
    else:
        st.caption(f"Logado via e-mail · {usuario.get('email', '')}")

    st.divider()
    st.info("Página principal em desenvolvimento.")

    if st.button("Sair"):
        _logout(tipo_auth)


def _logout(tipo_auth: str):
    for chave in ("logado", "usuario"):
        st.session_state.pop(chave, None)
    st.session_state["pagina"] = "login"

    if tipo_auth == "google":
        st.logout()   # limpa o token OAuth e redireciona
    else:
        st.rerun()