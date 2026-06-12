from __future__ import annotations

import re
from model.paciente_model import PacienteModel
from controller.arquivo_controller import ArquivoController


def _cpf_valido(cpf: str) -> bool:
    return len(re.sub(r"\D", "", cpf)) == 11


class PacienteController:

    @staticmethod
    def _validar_campos(nome: str, email: str) -> tuple[str | None, str | None]:
        """Retorna (nome_limpo, mensagem_de_erro). Erro é None se válido."""
        nome = (nome or "").strip()
        if not nome:
            return None, "O nome é obrigatório."
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return None, "E-mail inválido."
        return nome, None

    @staticmethod
    def _normalizar(sexo, data_nascimento, email, telefone, altura, peso, nota) -> tuple:
        return (
            sexo or None,
            data_nascimento or None,
            email.strip() if email else None,
            telefone.strip() if telefone else None,
            float(altura) if (altura and float(altura) > 0) else None,
            float(peso)   if (peso   and float(peso)   > 0) else None,
            nota.strip() if nota else None,
        )

    @staticmethod
    def cadastrar(usuario_id, nome, sexo, data_nascimento,
                  email, telefone, altura, peso, nota) -> tuple:
        nome_limpo, erro = PacienteController._validar_campos(nome, email)
        if erro:
            return False, erro, None
        try:
            pid = PacienteModel.criar(
                usuario_id, nome_limpo,
                *PacienteController._normalizar(
                    sexo, data_nascimento, email, telefone, altura, peso, nota
                ),
            )
            return True, "Paciente cadastrado com sucesso.", pid
        except Exception as e:
            return False, f"Erro ao cadastrar: {str(e)}", None

    @staticmethod
    def listar(usuario_id) -> list:
        return PacienteModel.listar(usuario_id)

    @staticmethod
    def buscar(paciente_id, usuario_id) -> dict | None:
        return PacienteModel.buscar(paciente_id, usuario_id)

    @staticmethod
    def atualizar(paciente_id, usuario_id, nome, sexo, data_nascimento,
                  email, telefone, altura, peso, nota) -> tuple:
        nome_limpo, erro = PacienteController._validar_campos(nome, email)
        if erro:
            return False, erro
        try:
            PacienteModel.atualizar(
                paciente_id, usuario_id, nome_limpo,
                *PacienteController._normalizar(
                    sexo, data_nascimento, email, telefone, altura, peso, nota
                ),
            )
            return True, "Paciente atualizado com sucesso."
        except Exception as e:
            return False, f"Erro ao atualizar: {str(e)}"

    @staticmethod
    def deletar(paciente_id, usuario_id) -> tuple:
        try:
            PacienteModel.deletar(paciente_id, usuario_id)
            return True, "Paciente removido com sucesso."
        except Exception as e:
            return False, f"Erro ao remover: {str(e)}"

    # ── Arquivos vinculados ───────────────────────────────────────────────────

    @staticmethod
    def listar_arquivos(paciente_id) -> list:
        return PacienteModel.listar_arquivos(paciente_id)

    @staticmethod
    def arquivos_disponiveis(usuario_id: int, paciente_id: int) -> tuple[list, list]:
        """
        Separa os arquivos do usuário em dois grupos:
        - disponíveis: sem vínculo ou já vinculados a este paciente
        - ocupados: vinculados a outro paciente
        """
        todos    = ArquivoController.listar(usuario_id)
        ocupados = PacienteModel.listar_arquivos_ocupados(usuario_id, paciente_id)
        ids_occ  = {o["arquivo_id"] for o in ocupados}
        return [a for a in todos if a["id"] not in ids_occ], ocupados

    @staticmethod
    def sincronizar_arquivos(paciente_id: int, novos_ids: list) -> tuple:
        """
        Garante que exatamente os arquivos em novos_ids estejam vinculados ao paciente.
        Rejeita arquivos já vinculados a outro paciente (regra: 1 arquivo → 1 paciente).
        """
        try:
            atuais     = {a["arquivo_id"] for a in PacienteModel.listar_arquivos(paciente_id)}
            novos      = set(novos_ids)
            a_vincular = novos - atuais

            if a_vincular:
                ocupados = PacienteModel.listar_arquivos_ocupados_por_ids(a_vincular)
                if ocupados:
                    detalhes = ", ".join(
                        f"'{o['arquivo_nome']}' (paciente: {o['paciente_nome']})"
                        for o in ocupados
                    )
                    return False, f"Arquivo(s) já vinculado(s) a outro paciente: {detalhes}."

            for aid in a_vincular:
                PacienteModel.vincular_arquivo(paciente_id, aid)
            for aid in atuais - novos:
                PacienteModel.desvincular_arquivo(paciente_id, aid)
            return True, "Arquivos atualizados."
        except Exception as e:
            return False, f"Erro ao atualizar arquivos: {str(e)}"
