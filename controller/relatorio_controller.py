"""Orquestração de relatórios exportados (tabela `relatorios`).

Camada intermediária entre as views e o `RelatorioModel`, responsável pelos
arquivos `.zip` salvos a cada exportação. Calcula o tamanho ao salvar e converte
o conteúdo BYTEA em `bytes` ao baixar.
"""

from model.relatorio_model import RelatorioModel


class RelatorioController:
    """Orquestra o ciclo de vida dos relatórios exportados."""

    @staticmethod
    def salvar(usuario_id: int, nome: str, arquivo_origem: str, conteudo: bytes) -> int:
        """Salva um relatório exportado, derivando o tamanho do conteúdo.

        Args:
            usuario_id: Id do usuário dono.
            nome: Nome do arquivo `.zip`.
            arquivo_origem: Nome do arquivo `.txt` de origem.
            conteudo: Conteúdo binário do `.zip`.

        Returns:
            int: Id do relatório salvo.
        """
        return RelatorioModel.salvar(usuario_id, nome, arquivo_origem, len(conteudo), conteudo)

    @staticmethod
    def listar(usuario_id: int) -> list:
        """Lista os relatórios de um usuário (metadados).

        Args:
            usuario_id: Id do usuário dono.

        Returns:
            list[dict]: Metadados dos relatórios.
        """
        return RelatorioModel.listar(usuario_id)

    @staticmethod
    def baixar(relatorio_id: int, usuario_id: int) -> tuple:
        """Recupera o conteúdo e o nome de um relatório para download.

        Args:
            relatorio_id: Id do relatório.
            usuario_id: Id do usuário dono.

        Returns:
            tuple: `(conteudo, nome)` em sucesso; `(None, mensagem)` se o
            relatório não for encontrado.
        """
        relatorio = RelatorioModel.buscar(relatorio_id, usuario_id)
        if not relatorio:
            return None, "Relatório não encontrado."
        return bytes(relatorio["conteudo"]), relatorio["nome"]

    @staticmethod
    def deletar(relatorio_id: int, usuario_id: int) -> tuple:
        """Remove um relatório do usuário.

        Args:
            relatorio_id: Id do relatório a remover.
            usuario_id: Id do usuário dono.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
        try:
            RelatorioModel.deletar(relatorio_id, usuario_id)
            return True, "Relatório removido com sucesso."
        except Exception as e:
            return False, f"Erro ao remover: {str(e)}"