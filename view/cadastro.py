"""
view/cadastro.py — Tela de cadastro de novos usuários.
"""

import streamlit as st
from controller.user_controller import UserController
from view.ui import Profissao, forca_senha


def cadastro_page():
    if st.session_state.get("cadastro_ok"):
        _tela_sucesso()
        return

    col_esq, col_dir = st.columns(2, border=True)

    with col_esq:
        st.header("Activity")
        st.subheader("Crie sua conta e comece a analisar.")
        st.write(
            "Acesse ferramentas de organização, filtragem e visualização de dados "
            "de actigrafia. Desenvolvido para pesquisadores e profissionais de saúde "
            "pela EACH-USP."
        )
        st.divider()
        st.write("Já tem uma conta?")
        if st.button("Fazer login", width="stretch"):
            st.session_state["pagina"] = "login"
            st.rerun()

    with col_dir:
        st.header("Faça seu cadastro")

        nome           = st.text_input("Nome completo", placeholder="João Silva")
        email          = st.text_input("E-mail", placeholder="xxxx@email.com")
        cpf            = st.text_input("CPF", placeholder="000.000.000-00", max_chars=14)
        profissao      = st.selectbox(
            "Profissão",
            Profissao.opcoes(),
            index=None,
            placeholder="Selecione uma profissão",
        )
        senha          = st.text_input("Senha", placeholder="Mínimo 6 caracteres", type="password")
        confirma_senha = st.text_input("Confirme a senha", placeholder="Repita a senha", type="password")

        if senha:
            score, label, emoji = forca_senha(senha)
            st.progress(score / 4, text=f"{emoji} Força da senha: **{label}**")

        if st.button("Criar conta", type="primary", width="stretch"):
            sucesso, mensagem = UserController.cadastrar(
                nome, email, cpf, senha, confirma_senha, profissao
            )
            if sucesso:
                st.session_state["cadastro_ok"] = True
                st.rerun()
            else:
                st.error(mensagem)


# ── Tela de sucesso ───────────────────────────────────────────────────────────

def _tela_sucesso():
    st.success("Conta criada com sucesso!")
    st.info("Sua conta está pronta. Faça o login para acessar o Activity.")
    if st.button("Ir para o login", type="primary", width="stretch"):
        st.session_state.pop("cadastro_ok", None)
        st.session_state["pagina"] = "login"
        st.rerun()