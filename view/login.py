import streamlit as st
from controller.user_controller import UserController


def login_page():
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
        </style>
        """, unsafe_allow_html=True)

        st.header("Activity")
        st.subheader("Faça suas análises sobre os dados de actigrafia.")
        st.write(
            "Organize, filtre e visualize dados de actigrafia de forma interativa "
            "e acessível. Ajudamos pesquisadores e profissionais de saúde a entregar "
            "relatórios claros, precisos e fundamentados."
        )

        container = st.container(border=True)
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
                # dias=0 → session cookie; dias=30 → cookie persistente de 30 dias
                dias  = 30 if manter_conectado else 0
                token = UserController.iniciar_sessao(usuario["id"], dias)

                st.session_state["usuario"]              = usuario
                st.session_state["usuario"]["tipo_auth"] = "email"
                st.session_state["logado"]               = True
                st.session_state["pagina"]               = "home"
                st.session_state["_session_token"]       = token
                st.session_state["_set_cookie"]          = {"token": token, "dias": dias}
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
