"""
controller/UserController.py — Lógica de negócio e validação para usuários.

Cada método retorna (bool, str) ou (bool, str, dict) para facilitar o tratamento
de erros nas views sem expor exceções brutas.
"""

import re
import bcrypt
from model.UserModel import UserModel
from model.SessaoModel import SessaoModel


class UserController:

    @staticmethod
    def cadastrar(nome, email, cpf, senha, confirma_senha, profissao):
        if not all([nome, email, cpf, senha, confirma_senha, profissao]):
            return False, "Preencha todos os campos."
        if senha != confirma_senha:
            return False, "As senhas não coincidem."
        if len(senha) < 6:
            return False, "A senha deve ter no mínimo 6 caracteres."
        if len(re.sub(r"\D", "", cpf)) != 11:
            return False, "CPF inválido."
        try:
            UserModel.criar_usuario(nome, email, cpf, senha, profissao)
            return True, "Cadastro realizado com sucesso!"
        except Exception as e:
            if "unique" in str(e).lower():
                return False, "Email ou CPF já cadastrado."
            return False, f"Erro ao cadastrar: {str(e)}"

    @staticmethod
    def login(email, senha):
        if not email or not senha:
            return False, "Preencha o email e a senha.", None
        usuario = UserModel.buscar_por_email(email)
        if not usuario:
            return False, "Email não encontrado.", None
        if not bcrypt.checkpw(senha.encode(), usuario["senha"].encode()):
            return False, "Senha incorreta.", None
        return True, "Login realizado com sucesso!", dict(usuario)

    @staticmethod
    def listar():
        return UserModel.listar_usuarios()

    @staticmethod
    def atualizar_perfil(user_id, nome, email, cpf, profissao,
                         telefone, data_nascimento, bio):
        if not all([nome, email, cpf, profissao]):
            return False, "Nome, e-mail, CPF e profissão são obrigatórios."
        if len(re.sub(r"\D", "", cpf)) != 11:
            return False, "CPF inválido."
        try:
            UserModel.atualizar_perfil(
                user_id, nome, email, cpf, profissao,
                telefone, data_nascimento, bio
            )
            return True, "Perfil atualizado com sucesso!"
        except Exception as e:
            if "unique" in str(e).lower():
                return False, "E-mail ou CPF já cadastrado para outro usuário."
            return False, f"Erro ao atualizar: {str(e)}"

    @staticmethod
    def atualizar_foto(user_id, foto_bytes, foto_nome, foto_tipo):
        try:
            UserModel.atualizar_foto(user_id, foto_bytes, foto_nome, foto_tipo)
            return True, "Foto atualizada com sucesso!"
        except Exception as e:
            return False, f"Erro ao atualizar foto: {str(e)}"

    @staticmethod
    def atualizar_senha(user_id, senha_atual, nova_senha, confirma_nova_senha):
        if not all([senha_atual, nova_senha, confirma_nova_senha]):
            return False, "Preencha todos os campos de senha."
        if nova_senha != confirma_nova_senha:
            return False, "As novas senhas não coincidem."
        if len(nova_senha) < 6:
            return False, "A nova senha deve ter no mínimo 6 caracteres."

        senha_hash_atual = UserModel.buscar_senha(user_id)
        if not senha_hash_atual:
            return False, "Usuário não encontrado."
        if not bcrypt.checkpw(senha_atual.encode(), senha_hash_atual.encode()):
            return False, "Senha atual incorreta."

        nova_hash = bcrypt.hashpw(nova_senha.encode(), bcrypt.gensalt()).decode()
        try:
            UserModel.atualizar_senha(user_id, nova_hash)
            return True, "Senha alterada com sucesso!"
        except Exception as e:
            return False, f"Erro ao alterar senha: {str(e)}"

    @staticmethod
    def deletar(user_id):
        try:
            UserModel.deletar_usuario(user_id)
            return True, "Usuário removido com sucesso!"
        except Exception as e:
            return False, f"Erro ao remover: {str(e)}"

    # ── Perfil ────────────────────────────────────────────────────────────────

    @staticmethod
    def buscar_perfil(usuario_id: int) -> dict | None:
        """Retorna o perfil completo pelo id."""
        return UserModel.buscar_por_id(usuario_id)

    @staticmethod
    def buscar_perfil_por_email(email: str) -> dict | None:
        """Retorna o perfil completo pelo e-mail (usado por contas Google sem id na sessão)."""
        return UserModel.buscar_por_email(email)

    # ── Sessão ────────────────────────────────────────────────────────────────

    @staticmethod
    def iniciar_sessao(usuario_id: int, dias: int) -> str:
        """Cria uma sessão persistente e retorna o token UUID."""
        return SessaoModel.criar(usuario_id, dias)

    @staticmethod
    def encerrar_sessao(token: str) -> None:
        """Invalida a sessão no banco (logout ou expiração forçada)."""
        SessaoModel.deletar(token)

    @staticmethod
    def restaurar_sessao(token: str) -> dict | None:
        """
        Valida o token e recarrega o perfil do usuário.
        Retorna o dict do usuário com tipo_auth='email', ou None se inválido/expirado.
        """
        uid = SessaoModel.buscar_usuario_id(token)
        if not uid:
            return None
        dados = UserModel.buscar_por_id(uid)
        if dados:
            dados["tipo_auth"] = "email"
        return dados
