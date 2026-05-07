import streamlit as st
from controller.UserController import UserController

def cadastro_page():
    with st.container():
        st.header("Faça seu cadastro")
        st.text("Preencha as informações abaixo para seu cadastro")

        nome           = st.text_input("Nome", placeholder="Nome Completo")
        email          = st.text_input("Email", placeholder="xxxx@email.com")
        cpf            = st.text_input("CPF", placeholder="CPF Completo")
        senha          = st.text_input("Crie sua senha", placeholder="**************", type="password")
        confirmaSenha  = st.text_input("Confirme sua senha", placeholder="**************", type="password")
        profissao      = st.selectbox(
            "Profissão",
            ("Médico", "Enfermeiro", "Fisioterapeuta", "Pesquisador", "Admin"),
            index=None,
            placeholder="Selecione uma profissão"
        )

        if st.button("Criar Conta ->", use_container_width=True):
            sucesso, mensagem = UserController.cadastrar(
                nome, email, cpf, senha, confirmaSenha, profissao
            )
            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)