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
        st.markdown("""
        <style>
        [data-testid="stColumn"]:first-of-type,
        [data-testid="stColumn"]:last-of-type {
            align-self: stretch;
        }
        [data-testid="stColumn"]:first-of-type > [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stColumn"]:last-of-type  > [data-testid="stVerticalBlockBorderWrapper"] {
            height: 100%;
        }
        [data-testid="stColumn"]:first-of-type > [data-testid="stVerticalBlockBorderWrapper"] > div,
        [data-testid="stColumn"]:last-of-type  > [data-testid="stVerticalBlockBorderWrapper"] > div {
            height: 100%;
            display: flex;
            flex-direction: column;
        }
        [data-testid="stColumn"]:first-of-type [data-testid="stVerticalBlock"]:first-of-type,
        [data-testid="stColumn"]:last-of-type  [data-testid="stVerticalBlock"]:first-of-type {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        [data-testid="stColumn"]:first-of-type [data-testid="stVerticalBlock"]:first-of-type > div:last-child {
            margin-top: auto;
        }
        [data-testid="stBaseButton-primary"] {
            background-color: #1a3a5c;
            border-color: #1a3a5c;
        }
        [data-testid="stBaseButton-primary"]:hover {
            background-color: #142d4a;
            border-color: #142d4a;
        }
        </style>
        """, unsafe_allow_html=True)

        col_logo, col_titulo = st.columns([1, 14], vertical_alignment="center")
        col_logo.image("imagens/spring.png", width=50)
        col_titulo.markdown(
            "<div style='padding-left:0.1rem; display:flex; flex-direction:column; justify-content:center; height:100%; margin-top:-1.3rem'>"
            "<h1 style='margin:0'>Activity</h1>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='font-size:1.9rem; font-weight:700; margin:1.7rem 0 1rem 0'>"
            "Crie sua conta "
            "<span style='color:#1a3a5c'>e comece a analisar</span>."
            "</p>"
            "<p style='font-size:1.15rem; line-height:2.0; margin:0'>"
            "Acesse ferramentas de organização, filtragem e visualização de dados "
            "de actigrafia. Desenvolvido para pesquisadores e profissionais de saúde "
            "pela EACH-USP."
            "</p>",
            unsafe_allow_html=True,
        )

        with st.container(border=False):
            st.markdown("<div style='text-align:center; margin-bottom:0.6rem'>Já tem uma conta?</div>", unsafe_allow_html=True)
            if st.button("Fazer login", width="stretch"):
                st.session_state["pagina"] = "login"
                st.rerun()

    with col_dir:
        st.header("Faça seu cadastro")

        nome           = st.text_input("Nome completo", placeholder="João Silva")
        email          = st.text_input("E-mail", placeholder="xxxx@email.com")
        col_cpf, col_prof = st.columns(2)
        cpf       = col_cpf.text_input("CPF", placeholder="000.000.000-00", max_chars=14)
        profissao = col_prof.selectbox(
            "Profissão",
            Profissao.opcoes(),
            index=None,
            placeholder="Selecione uma profissão",
        )
        col_senha, col_confirma = st.columns(2)
        senha          = col_senha.text_input("Senha", placeholder="Mínimo 6 caracteres", type="password")
        confirma_senha = col_confirma.text_input("Confirme a senha", placeholder="Repita a senha", type="password")

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