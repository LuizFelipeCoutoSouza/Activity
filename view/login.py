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

"""Tela de login da aplicação.

Layout em duas colunas: à esquerda, a apresentação do produto; à direita, o
formulário de autenticação. No login bem-sucedido, inicia a sessão persistente e
agenda a gravação do cookie, deixando a escrita efetiva para o próximo render em
`app.py`.
"""

import streamlit as st
from controller.user_controller import UserController


def login_page():
    """Renderiza a página de login e processa a tentativa de autenticação.

    Em caso de sucesso, cria a sessão (com validade conforme "manter conectado"),
    grava os dados em `st.session_state`, agenda o cookie e força o rerun. Em
    falha, exibe a mensagem de erro retornada pelo controller.
    """
    col_esq, col_dir = st.columns(2, border=True)

    with col_esq:
        st.markdown("""
        <style>
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
        [data-testid="stColumn"]:last-of-type [data-testid="stVerticalBlock"]:first-of-type > div:last-child {
            margin-top: auto;
            margin-bottom: auto;
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
            "Faça suas análises "
            "<span style='color:#1a3a5c'>sobre os dados de actigrafia</span>."
            "</p>"
            "<p style='font-size:1.15rem; line-height:2.0; margin:0'>"
            "Organize, filtre e visualize dados de actigrafia de forma interativa "
            "e acessível. Ajudamos pesquisadores e profissionais de saúde a entregar "
            "relatórios claros, precisos e fundamentados."
            "</p>",
            unsafe_allow_html=True,
        )

        container = st.container(border=False)
        with container:
            col_img, col_txt = st.columns([1, 5], vertical_alignment="center")
            col_img.image("imagens/Logo_EACH-USP.png", width=100)
            col_txt.markdown(
                "<div style='padding-left:0.1rem; display:flex; flex-direction:column; justify-content:center; height:100%; margin-top:-0.9rem'>"
                "<strong>Pensado e desenvolvido pela EACH-USP</strong>"
                "<br><span style='font-size:0.8rem; color:gray'>Projeto Supervisionado de Graduação I</span>"
                "</div>",
                unsafe_allow_html=True,
            )

    with col_dir:
        st.header("Bem-vindo!")
        st.write("Acesse o portal fazendo o login abaixo.")

        email            = st.text_input("E-mail", placeholder="xxxx@email.com")
        senha            = st.text_input("Senha", placeholder="Sua senha", type="password")
        manter_conectado = st.checkbox("Manter conectado por 30 dias")

        if st.button("Entrar", type="primary", width="stretch"):
            sucesso, mensagem, usuario = UserController.login(email, senha)
            if sucesso:
                # 30 dias → cookie persistente; 0 → session cookie (fecha com o navegador).
                dias  = 30 if manter_conectado else 0
                token = UserController.iniciar_sessao(usuario["id"], dias)

                st.session_state["usuario"]        = usuario
                st.session_state["logado"]         = True
                st.session_state["pagina"]         = "home"
                st.session_state["_session_token"] = token
                st.session_state["_set_cookie"]    = {"token": token, "dias": dias}
                st.rerun()
            else:
                st.error(mensagem)

        st.divider()

        st.markdown("<div style='text-align:center; margin-bottom:0.6rem'>Novo na plataforma?</div>", unsafe_allow_html=True)
        if st.button("Criar uma conta", width="stretch"):
            st.session_state["pagina"] = "cadastro"
            st.rerun()

        st.markdown(
            "<div style='text-align:center'>"
            "<a href='https://www.google.com'>Privacidade</a>"
            " &nbsp;·&nbsp; "
            "<a href='https://www.google.com'>Segurança</a>"
            " &nbsp;·&nbsp; "
            "<a href='https://www.google.com'>Ajuda</a>"
            "</div>",
            unsafe_allow_html=True,
        )
