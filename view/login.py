import streamlit as st
from controller.UserController import UserController


def login_page():
    col_esq, col_dir = st.columns(2, border=True)

    with col_esq:
        st.header("Activity")
        st.subheader("Faça suas análises sobre os dados de actigrafia.")
        st.write(
            "Organize, filtre e visualize dados de actigrafia de forma interativa "
            "e acessível. Ajudamos pesquisadores e profissionais de saúde a entregar "
            "relatórios claros, precisos e fundamentados."
        )
        container = st.container(border=True)
        with container:
            st.write("Pensado e desenvolvido pela EACH-USP")
            st.write("Ana Amélia, Laila e Luiz :)")

        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.markdown("[Privacidade](https://www.google.com)")
        col2.markdown("[Segurança](https://www.google.com)")
        col3.markdown("[Ajuda](https://www.google.com)")

    with col_dir:
        st.header("Bem-vindo!")
        st.write("Acesse o portal fazendo o login abaixo.")

        email           = st.text_input("E-mail", placeholder="xxxx@email.com")
        senha           = st.text_input("Senha", placeholder="Sua senha", type="password")
        manter_conectado = st.checkbox("Manter conectado por 30 dias")

        if st.button("Entrar", type="primary", use_container_width=True):
            sucesso, mensagem, usuario = UserController.login(email, senha)
            if sucesso:
                st.session_state["usuario"]              = usuario
                st.session_state["usuario"]["tipo_auth"] = "email"
                st.session_state["logado"]               = True
                st.session_state["pagina"]               = "home"
                st.rerun()
            else:
                st.error(mensagem)

        st.caption("— ou —")

        if st.button("Entrar com Google", use_container_width=True):
            st.login()

        st.divider()

        st.write("Novo na plataforma?")
        if st.button("Criar uma conta", use_container_width=True):
            st.session_state["pagina"] = "cadastro"
            st.rerun()
