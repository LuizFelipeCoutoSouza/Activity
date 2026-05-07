import streamlit as st
from controller.UserController import UserController

def login_page():
    col_esquerda, col_direita = st.columns(2, border=True, gap=None)

    with col_esquerda:
        st.header("Activity")
        st.subheader("Faça suas análises sobre os dados de actigrafia.")
        st.write("Organize, filtre e visualize dados de actigrafia de forma interativa e acessível. Ajudamos pesquisadores e profissionais de saúde a entregar relatórios claros, precisos e fundamentados.")
        container = st.container(border=True)
        with container:
            st.write("Pensado e desenvolvido pela EACH-USP")
            st.write("Ana Amélia, Laila e Luiz :)")

    with col_direita:
        st.header("Bem vindo de volta")
        st.write("Acesse o portal fazendo o login abaixo.")

        email          = st.text_input("Email", placeholder="xxxx@email.com")
        senha          = st.text_input("Senha", placeholder="**************", type="password")
        mante_conectado = st.checkbox("Manter conectado por 30 dias")

        if st.button("Login ->", use_container_width=True):
            sucesso, mensagem, usuario = UserController.login(email, senha)
            if sucesso:
                st.success(f"✅ {mensagem} Olá, {usuario['nome']}!")
                # Salva na sessão para uso futuro
                st.session_state["usuario"] = usuario
                st.session_state["logado"] = True
            else:
                st.error(f"❌ {mensagem}")

        st.divider()

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.write("Novo na plataforma?")
            if st.button("Faça seu cadastro", use_container_width=True):
                st.session_state["pagina"] = "cadastro"
                st.rerun()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("[Protocolo de Privacidade](https://www.google.com)")
        with col2:
            st.markdown("[Padrões de Segurança](https://www.google.com)")
        with col3:
            st.markdown("[Central de Ajuda](https://www.google.com)")