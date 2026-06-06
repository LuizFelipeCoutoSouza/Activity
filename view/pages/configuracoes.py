"""
view/pages/configuracoes.py — Página de configurações de perfil do usuário.

Seções:
  - Perfil : foto, dados pessoais e profissionais
  - Segurança: troca de senha (somente contas e-mail)
"""

import streamlit as st
from datetime import date

from controller.UserController import UserController
from view.ui import (
    Profissao,
    AVATAR_SM, AVATAR_LG,
    fmt_cpf, fmt_telefone, forca_senha,
    img_b64_tag, avatar_html,
    set_toast, render_toast,
)

FOTO_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
FOTO_TIPOS     = ["jpg", "jpeg", "png"]


# ── Entrada principal ─────────────────────────────────────────────────────────

def configuracoes_page():
    usuario   = st.session_state.get("usuario", {})
    email     = usuario.get("email")
    tipo_auth = usuario.get("tipo_auth", "email")

    dados = UserController.buscar_perfil_por_email(email)
    if not dados:
        st.error("Dados do usuário não encontrados.")
        return

    render_toast()

    _cabecalho(dados)
    st.divider()

    tab_perfil, tab_seguranca = st.tabs(["Perfil", "Segurança"])

    with tab_perfil:
        _secao_foto(dados)
        st.divider()
        _formulario_perfil(dados, tipo_auth)

    with tab_seguranca:
        _secao_senha(dados, tipo_auth)


# ── Cabeçalho ─────────────────────────────────────────────────────────────────

def _cabecalho(dados: dict):
    col_foto, col_info = st.columns([1, 6])

    with col_foto:
        st.markdown(
            avatar_html(dados.get("nome", ""), dados.get("foto_perfil"), dados.get("foto_tipo"), AVATAR_SM),
            unsafe_allow_html=True,
        )

    with col_info:
        st.markdown(f"### {dados.get('nome', 'Usuário')}")
        bio  = dados.get("bio") or ""
        desc = dados.get("profissao", "")
        if bio:
            desc += f"  ·  {bio[:60]}{'...' if len(bio) > 60 else ''}"
        st.caption(desc)


# ── Foto de perfil ─────────────────────────────────────────────────────────────

def _secao_foto(dados: dict):
    st.subheader("Foto de perfil")

    col_atual, col_upload = st.columns([1, 3], gap="large")

    with col_atual:
        st.markdown(
            avatar_html(dados.get("nome", ""), dados.get("foto_perfil"), dados.get("foto_tipo"), AVATAR_LG),
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if dados.get("foto_perfil"):
            if st.button("Remover foto", width="stretch"):
                ok, msg = UserController.atualizar_foto(dados["id"], None, None, None)
                if ok:
                    _sync_sessao_foto(None, None)
                    set_toast("Foto removida.")
                    st.rerun()
                else:
                    st.error(msg)

    with col_upload:
        arquivo = st.file_uploader(
            "Enviar nova foto",
            type=FOTO_TIPOS,
            help=f"PNG ou JPEG · máx. {FOTO_MAX_BYTES // (1024 * 1024)} MB",
        )

        if arquivo is not None:
            if arquivo.size > FOTO_MAX_BYTES:
                st.error(
                    f"A foto excede o limite de {FOTO_MAX_BYTES // (1024 * 1024)} MB "
                    f"(enviado: {arquivo.size / (1024 * 1024):.1f} MB)."
                )
            else:
                foto_preview = arquivo.read()
                arquivo.seek(0)
                st.markdown(
                    img_b64_tag(foto_preview, arquivo.type, AVATAR_LG, "Pré-visualização"),
                    unsafe_allow_html=True,
                )

                if st.button("Salvar foto", type="primary"):
                    foto_bytes = arquivo.read()
                    ok, msg = UserController.atualizar_foto(
                        dados["id"], foto_bytes, arquivo.name, arquivo.type
                    )
                    if ok:
                        _sync_sessao_foto(foto_bytes, arquivo.type)
                        set_toast(msg)
                        st.rerun()
                    else:
                        st.error(msg)


# ── Formulário de perfil ───────────────────────────────────────────────────────

def _formulario_perfil(dados: dict, tipo_auth: str):
    st.subheader("Dados do perfil")

    with st.form("form_perfil"):
        nome = st.text_input("Nome completo *", value=dados.get("nome") or "")

        col1, col2 = st.columns(2)

        with col1:
            email = st.text_input(
                "E-mail *",
                value=dados.get("email") or "",
                disabled=tipo_auth == "google",
                help="Conta Google: e-mail gerenciado pelo Google.",
            )
            cpf = st.text_input(
                "CPF *",
                value=fmt_cpf(dados.get("cpf")),
                max_chars=14,
                placeholder="000.000.000-00",
            )

        with col2:
            profissao_atual = dados.get("profissao") or Profissao.opcoes()[0]
            idx = Profissao.opcoes().index(profissao_atual) if profissao_atual in Profissao.opcoes() else 0
            profissao = st.selectbox("Profissão *", Profissao.opcoes(), index=idx)
            telefone  = st.text_input(
                "Telefone",
                value=fmt_telefone(dados.get("telefone")),
                max_chars=15,
                placeholder="(00) 00000-0000",
            )

        data_nasc_atual = dados.get("data_nascimento")
        data_nascimento = st.date_input(
            "Data de nascimento",
            value=data_nasc_atual if data_nasc_atual else None,
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            format="DD/MM/YYYY",
        )

        bio = st.text_area(
            "Bio",
            value=dados.get("bio") or "",
            placeholder="Breve descrição sobre você...",
            max_chars=500,
            height=100,
        )

        st.caption("* Campos obrigatórios")

        if st.form_submit_button("Salvar alterações", type="primary", width="stretch"):
            email_salvo = dados["email"] if tipo_auth == "google" else email
            ok, msg = UserController.atualizar_perfil(
                dados["id"], nome, email_salvo, cpf, profissao,
                telefone, data_nascimento if data_nascimento else None, bio,
            )
            if ok:
                if "usuario" in st.session_state:
                    st.session_state["usuario"].update(
                        {"nome": nome, "email": email_salvo, "profissao": profissao}
                    )
                set_toast(msg)
                st.rerun()
            else:
                st.error(msg)


# ── Segurança / senha ──────────────────────────────────────────────────────────

def _secao_senha(dados: dict, tipo_auth: str):
    st.subheader("Alterar senha")

    if tipo_auth == "google":
        st.info(
            "Sua conta usa autenticação Google. "
            "A senha é gerenciada pelo Google e não pode ser alterada aqui."
        )
        return

    with st.form("form_senha"):
        senha_atual = st.text_input("Senha atual",         type="password", placeholder="Digite sua senha atual")
        nova_senha  = st.text_input("Nova senha",          type="password", placeholder="Mínimo 6 caracteres")
        confirma    = st.text_input("Confirmar nova senha", type="password", placeholder="Repita a nova senha")

        if nova_senha:
            score, label, emoji = forca_senha(nova_senha)
            st.progress(score / 4, text=f"{emoji} Força: **{label}**")

        if st.form_submit_button("Alterar senha", type="primary", width="stretch"):
            ok, msg = UserController.atualizar_senha(dados["id"], senha_atual, nova_senha, confirma)
            if ok:
                set_toast(msg)
                st.rerun()
            else:
                st.error(msg)


# ── Helpers internos ──────────────────────────────────────────────────────────

def _sync_sessao_foto(foto_bytes: bytes | None, foto_tipo: str | None) -> None:
    """Mantém a foto do perfil em session_state sincronizada com o banco."""
    if "usuario" in st.session_state:
        st.session_state["usuario"]["foto_perfil"] = foto_bytes
        st.session_state["usuario"]["foto_tipo"]   = foto_tipo