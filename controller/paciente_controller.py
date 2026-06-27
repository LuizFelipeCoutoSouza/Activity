# -----------------------------------------------------------------------------
# Activity — Sistema web para análise de dados de actigrafia
#
# Monografia apresentada à Escola de Artes, Ciências e Humanidades da
# Universidade de São Paulo, como parte dos requisitos exigidos na disciplina
# ACH2017 — Projeto Supervisionado ou de Graduação I, para obtenção do título
# de Bacharelado em Sistemas de Informação.
#
# Modalidade: TCC curto (1 semestre) — em grupo
#
# Autores:
#   Laila Malafaia Vieira
#   Luiz Felipe Couto de Souza
#
# Orientadora: Profa. Dra. Ana Amélia Benedito Silva
#
# São Paulo, 2026
# -----------------------------------------------------------------------------

"""Validação e orquestração de pacientes e seus vínculos com arquivos.

Camada intermediária entre as views e os modelos `PacienteModel`/`ArquivoController`.
Valida e normaliza os dados de paciente e aplica a regra de negócio "um arquivo
pertence a no máximo um paciente". As operações seguem o padrão de retorno em
tupla.
"""

from __future__ import annotations

import re
from model.paciente_model import PacienteModel
from controller.arquivo_controller import ArquivoController


def _cpf_valido(cpf: str) -> bool:
    """Verifica se o CPF contém 11 dígitos, ignorando a máscara.

    Args:
        cpf: CPF com ou sem máscara.

    Returns:
        bool: True se sobrarem exatamente 11 dígitos.
    """
    return len(re.sub(r"\D", "", cpf)) == 11


class PacienteController:
    """Orquestra o CRUD de pacientes e a sincronização de arquivos vinculados."""

    @staticmethod
    def _validar_campos(nome: str, email: str) -> tuple[str | None, str | None]:
        """Valida nome e e-mail de um paciente.

        Args:
            nome: Nome a validar (obrigatório, sem espaços nas pontas).
            email: E-mail a validar (opcional; se presente, deve ter formato válido).

        Returns:
            tuple[str | None, str | None]: `(nome_limpo, erro)`. Se válido,
            `nome_limpo` traz o nome sem espaços e `erro` é None; se inválido,
            `nome_limpo` é None e `erro` traz a mensagem.
        """
        nome = (nome or "").strip()
        if not nome:
            return None, "O nome é obrigatório."
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return None, "E-mail inválido."
        return nome, None

    @staticmethod
    def _normalizar(sexo, data_nascimento, email, telefone, altura, peso, nota) -> tuple:
        """Converte campos opcionais para a forma de persistência.

        Strings vazias viram None; altura e peso viram float positivo ou None.

        Args:
            sexo: Sexo informado.
            data_nascimento: Data de nascimento.
            email: E-mail.
            telefone: Telefone.
            altura: Altura (string ou número); descartada se não for positiva.
            peso: Peso (string ou número); descartado se não for positivo.
            nota: Anotação livre.

        Returns:
            tuple: Valores normalizados na ordem
            `(sexo, data_nascimento, email, telefone, altura, peso, nota)`.
        """
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
        """Valida, normaliza e cria um paciente.

        Args:
            usuario_id: Id do usuário (profissional) dono.
            nome: Nome do paciente (obrigatório).
            sexo: Sexo.
            data_nascimento: Data de nascimento.
            email: E-mail (validado se informado).
            telefone: Telefone.
            altura: Altura em centímetros.
            peso: Peso em quilogramas.
            nota: Anotação livre.

        Returns:
            tuple[bool, str, int | None]: `(sucesso, mensagem, paciente_id)`. Em
            falha de validação ou erro, o id é None.
        """
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
        """Lista os pacientes do usuário com a contagem de arquivos vinculados.

        Args:
            usuario_id: Id do usuário dono.

        Returns:
            list[dict]: Pacientes com a coluna `num_arquivos`.
        """
        return PacienteModel.listar(usuario_id)

    @staticmethod
    def buscar(paciente_id, usuario_id) -> dict | None:
        """Busca um paciente pelo id.

        Args:
            paciente_id: Id do paciente.
            usuario_id: Id do usuário dono.

        Returns:
            dict | None: Dados do paciente, ou None se não encontrado.
        """
        return PacienteModel.buscar(paciente_id, usuario_id)

    @staticmethod
    def atualizar(paciente_id, usuario_id, nome, sexo, data_nascimento,
                  email, telefone, altura, peso, nota) -> tuple:
        """Valida, normaliza e persiste alterações de um paciente.

        Args:
            paciente_id: Id do paciente a atualizar.
            usuario_id: Id do usuário dono.
            nome: Novo nome (obrigatório).
            sexo: Novo sexo.
            data_nascimento: Nova data de nascimento.
            email: Novo e-mail (validado se informado).
            telefone: Novo telefone.
            altura: Nova altura em centímetros.
            peso: Novo peso em quilogramas.
            nota: Nova anotação livre.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
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
        """Remove um paciente (os arquivos são desvinculados, não apagados).

        Args:
            paciente_id: Id do paciente a remover.
            usuario_id: Id do usuário dono.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
        try:
            PacienteModel.deletar(paciente_id, usuario_id)
            return True, "Paciente removido com sucesso."
        except Exception as e:
            return False, f"Erro ao remover: {str(e)}"

    # ── Arquivos vinculados ───────────────────────────────────────────────────

    @staticmethod
    def listar_arquivos(paciente_id) -> list:
        """Lista os arquivos vinculados a um paciente.

        Args:
            paciente_id: Id do paciente.

        Returns:
            list[dict]: Arquivos vinculados.
        """
        return PacienteModel.listar_arquivos(paciente_id)

    @staticmethod
    def arquivos_disponiveis(usuario_id: int, paciente_id: int) -> tuple[list, list]:
        """Separa os arquivos do usuário entre disponíveis e ocupados.

        Args:
            usuario_id: Id do usuário dono.
            paciente_id: Id do paciente em edição.

        Returns:
            tuple[list, list]: `(disponiveis, ocupados)`. `disponiveis` reúne os
            arquivos sem vínculo ou já vinculados a este paciente; `ocupados`,
            os vinculados a outros pacientes.
        """
        todos    = ArquivoController.listar(usuario_id)
        ocupados = PacienteModel.listar_arquivos_ocupados(usuario_id, paciente_id)
        ids_occ  = {o["arquivo_id"] for o in ocupados}
        return [a for a in todos if a["id"] not in ids_occ], ocupados

    @staticmethod
    def sincronizar_arquivos(paciente_id: int, novos_ids: list) -> tuple:
        """Ajusta os vínculos do paciente para coincidir com `novos_ids`.

        Calcula a diferença em relação aos vínculos atuais e vincula/desvincula o
        necessário. Rejeita a operação inteira se algum arquivo a vincular já
        pertencer a outro paciente (regra: 1 arquivo → 1 paciente).

        Args:
            paciente_id: Id do paciente.
            novos_ids: Conjunto desejado de ids de arquivo vinculados.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`. Em conflito, a mensagem
            detalha os arquivos já vinculados a outros pacientes.
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
