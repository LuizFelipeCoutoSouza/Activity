import streamlit as st
from controller.UserController import UserController


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
        if st.button("Fazer login", use_container_width=True):
            st.session_state["pagina"] = "login"
            st.rerun()

    with col_dir:
        st.header("Faça seu cadastro")

        nome           = st.text_input("Nome completo", placeholder="João Silva")
        email          = st.text_input("E-mail", placeholder="xxxx@email.com")
        cpf            = st.text_input("CPF", placeholder="000.000.000-00", max_chars=14)
        profissao      = st.selectbox(
            "Profissão",
            ("Médico", "Enfermeiro", "Fisioterapeuta", "Pesquisador"),
            index=None,
            placeholder="Selecione uma profissão",
        )
        senha          = st.text_input("Senha", placeholder="Mínimo 6 caracteres", type="password")
        confirma_senha = st.text_input("Confirme a senha", placeholder="Repita a senha", type="password")

        if senha:
            score, label, emoji = _forca_senha(senha)
            st.progress(score / 4, text=f"{emoji} Força da senha: **{label}**")

        if st.button("Criar conta", type="primary", use_container_width=True):
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
    if st.button("Ir para o login", type="primary", use_container_width=True):
        st.session_state.pop("cadastro_ok", None)
        st.session_state["pagina"] = "login"
        st.rerun()


# ── Força de senha ────────────────────────────────────────────────────────────

def _forca_senha(senha: str) -> tuple:
    score = 0
    if len(senha) >= 6:
        score += 1
    if len(senha) >= 10:
        score += 1
    if any(c.isupper() for c in senha):
        score += 1
    if any(c.isdigit() or not c.isalnum() for c in senha):
        score += 1
    tabela = {
        0: ("🔴", "Muito fraca"),
        1: ("🔴", "Fraca"),
        2: ("🟠", "Razoável"),
        3: ("🟡", "Boa"),
        4: ("🟢", "Forte"),
    }
    emoji, label = tabela[score]
    return score, label, emoji
