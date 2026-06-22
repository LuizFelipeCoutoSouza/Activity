"""Lógica de negócio e validação para usuários e sessões.

Camada intermediária entre as views e os modelos `UserModel`/`SessaoModel`. As
operações com validação retornam tuplas no padrão `(bool, str)` ou
`(bool, str, dict)` — sucesso, mensagem ao usuário e, quando aplicável, dados —,
permitindo às views tratar erros sem lidar com exceções brutas.
"""

from __future__ import annotations

import re
import bcrypt
from model.user_model import UserModel
from model.sessao_model import SessaoModel


def _cpf_valido(cpf: str) -> bool:
    """Verifica se o CPF contém 11 dígitos, ignorando a máscara.

    Args:
        cpf: CPF com ou sem máscara.

    Returns:
        bool: True se sobrarem exatamente 11 dígitos. Não valida os dígitos
        verificadores.
    """
    return len(re.sub(r"\D", "", cpf)) == 11


class UserController:
    """Orquestra cadastro, autenticação, perfil e sessões de usuário."""

    @staticmethod
    def cadastrar(nome, email, cpf, senha, confirma_senha, profissao):
        """Valida os dados de cadastro e cria o usuário.

        Verifica preenchimento, confirmação e tamanho mínimo de senha e validade
        do CPF antes de delegar a inserção ao modelo.

        Args:
            nome: Nome completo.
            email: E-mail (único).
            cpf: CPF (único).
            senha: Senha em texto puro (mínimo de 6 caracteres).
            confirma_senha: Repetição da senha, que deve coincidir.
            profissao: Profissão do usuário.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`. Em caso de e-mail/CPF já
            cadastrados, retorna False com mensagem apropriada.
        """
        if not all([nome, email, cpf, senha, confirma_senha, profissao]):
            return False, "Preencha todos os campos."
        if senha != confirma_senha:
            return False, "As senhas não coincidem."
        if len(senha) < 6:
            return False, "A senha deve ter no mínimo 6 caracteres."
        if not _cpf_valido(cpf):
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
        """Autentica um usuário por e-mail e senha.

        Args:
            email: E-mail informado.
            senha: Senha em texto puro, comparada com o hash bcrypt armazenado.

        Returns:
            tuple[bool, str, dict | None]: `(sucesso, mensagem, usuario)`. Em
            sucesso, `usuario` é o dict de perfil; em falha, é None.
        """
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
        """Lista todos os usuários cadastrados.

        Returns:
            list[dict]: Usuários com dados de perfil básicos.
        """
        return UserModel.listar_usuarios()

    @staticmethod
    def atualizar_perfil(user_id, nome, email, cpf, profissao,
                         telefone, data_nascimento, bio):
        """Valida e persiste alterações no perfil de um usuário.

        Args:
            user_id: Id do usuário a atualizar.
            nome: Novo nome (obrigatório).
            email: Novo e-mail (obrigatório).
            cpf: Novo CPF (obrigatório, validado).
            profissao: Nova profissão (obrigatória).
            telefone: Novo telefone.
            data_nascimento: Nova data de nascimento.
            bio: Nova biografia.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`. Retorna False se um campo
            obrigatório faltar, se o CPF for inválido ou se e-mail/CPF colidirem
            com outro usuário.
        """
        if not all([nome, email, cpf, profissao]):
            return False, "Nome, e-mail, CPF e profissão são obrigatórios."
        if not _cpf_valido(cpf):
            return False, "CPF inválido."
        try:
            UserModel.atualizar_perfil(
                user_id, nome, email, cpf, profissao,
                telefone, data_nascimento, bio,
            )
            return True, "Perfil atualizado com sucesso!"
        except Exception as e:
            if "unique" in str(e).lower():
                return False, "E-mail ou CPF já cadastrado para outro usuário."
            return False, f"Erro ao atualizar: {str(e)}"

    @staticmethod
    def atualizar_foto(user_id, foto_bytes, foto_nome, foto_tipo):
        """Persiste a foto de perfil de um usuário.

        Args:
            user_id: Id do usuário.
            foto_bytes: Conteúdo binário da imagem.
            foto_nome: Nome do arquivo de imagem.
            foto_tipo: Tipo MIME da imagem.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
        try:
            UserModel.atualizar_foto(user_id, foto_bytes, foto_nome, foto_tipo)
            return True, "Foto atualizada com sucesso!"
        except Exception as e:
            return False, f"Erro ao atualizar foto: {str(e)}"

    @staticmethod
    def atualizar_senha(user_id, senha_atual, nova_senha, confirma_nova_senha):
        """Valida a senha atual e grava a nova como hash bcrypt.

        Confere preenchimento, coincidência e tamanho mínimo da nova senha, além
        de validar a senha atual antes de persistir.

        Args:
            user_id: Id do usuário.
            senha_atual: Senha atual em texto puro, conferida contra o hash.
            nova_senha: Nova senha (mínimo de 6 caracteres).
            confirma_nova_senha: Repetição da nova senha, que deve coincidir.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
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
        """Remove um usuário.

        Args:
            user_id: Id do usuário a remover.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
        try:
            UserModel.deletar_usuario(user_id)
            return True, "Usuário removido com sucesso!"
        except Exception as e:
            return False, f"Erro ao remover: {str(e)}"

    # ── Perfil ────────────────────────────────────────────────────────────────

    @staticmethod
    def buscar_perfil(usuario_id: int) -> dict | None:
        """Retorna o perfil completo de um usuário pelo id.

        Args:
            usuario_id: Id do usuário.

        Returns:
            dict | None: Dados do perfil, ou None se não encontrado.
        """
        return UserModel.buscar_por_id(usuario_id)

    @staticmethod
    def buscar_perfil_por_email(email: str) -> dict | None:
        """Retorna o perfil de um usuário pelo e-mail.

        Args:
            email: E-mail do usuário.

        Returns:
            dict | None: Dados do usuário (inclui o hash da senha), ou None se
            não encontrado.
        """
        return UserModel.buscar_por_email(email)

    # ── Sessão ────────────────────────────────────────────────────────────────

    @staticmethod
    def iniciar_sessao(usuario_id: int, dias: int) -> str:
        """Cria uma sessão persistente e retorna o token.

        Args:
            usuario_id: Id do usuário autenticado.
            dias: Validade em dias (0 para sessão de duração curta).

        Returns:
            str: Token UUID da sessão criada.
        """
        return SessaoModel.criar(usuario_id, dias)

    @staticmethod
    def encerrar_sessao(token: str) -> None:
        """Invalida uma sessão no banco (logout).

        Args:
            token: Token UUID da sessão a encerrar.
        """
        SessaoModel.deletar(token)

    @staticmethod
    def restaurar_sessao(token: str) -> dict | None:
        """Valida um token de sessão e recarrega o perfil do usuário.

        Args:
            token: Token UUID lido do cookie.

        Returns:
            dict | None: Perfil do usuário se o token for válido e não expirado;
            None caso contrário.
        """
        uid = SessaoModel.buscar_usuario_id(token)
        if not uid:
            return None
        return UserModel.buscar_por_id(uid)
