import bcrypt
from model.UserModel import UserModel

class UserController:

    @staticmethod
    def cadastrar(nome, email, cpf, senha, confirma_senha, profissao):
        # Validações
        if not all([nome, email, cpf, senha, confirma_senha, profissao]):
            return False, "Preencha todos os campos."
        if senha != confirma_senha:
            return False, "As senhas não coincidem."
        if len(senha) < 6:
            return False, "A senha deve ter no mínimo 6 caracteres."
        if len(cpf) < 11:
            return False, "CPF inválido."

        try:
            UserModel.criar_usuario(nome, email, cpf, senha, profissao)
            return True, "Cadastro realizado com sucesso!"
        except Exception as e:
            if "unique" in str(e).lower():
                return False, "Email ou CPF já cadastrado."
            return False, f"Erro ao cadastrar: {str(e)}"

    @staticmethod
    def listar():
        return UserModel.listar_usuarios()

    @staticmethod
    def atualizar(user_id, nome, email, cpf, profissao):
        try:
            UserModel.atualizar_usuario(user_id, nome, email, cpf, profissao)
            return True, "Usuário atualizado com sucesso!"
        except Exception as e:
            return False, f"Erro ao atualizar: {str(e)}"

    @staticmethod
    def deletar(user_id):
        try:
            UserModel.deletar_usuario(user_id)
            return True, "Usuário removido com sucesso!"
        except Exception as e:
            return False, f"Erro ao remover: {str(e)}"

    @staticmethod
    def login(email, senha):
        if not email or not senha:
            return False, "Preencha o email e a senha.", None

        usuario = UserModel.buscar_por_email(email)

        if not usuario:
            return False, "Email não encontrado.", None

        senha_correta = bcrypt.checkpw(senha.encode(), usuario["senha"].encode())

        if not senha_correta:
            return False, "Senha incorreta.", None

        return True, "Login realizado com sucesso!", dict(usuario)