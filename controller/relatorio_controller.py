from model.relatorio_model import RelatorioModel


class RelatorioController:

    @staticmethod
    def salvar(usuario_id: int, nome: str, arquivo_origem: str, conteudo: bytes) -> int:
        return RelatorioModel.salvar(usuario_id, nome, arquivo_origem, len(conteudo), conteudo)

    @staticmethod
    def listar(usuario_id: int) -> list:
        return RelatorioModel.listar(usuario_id)

    @staticmethod
    def baixar(relatorio_id: int, usuario_id: int) -> tuple:
        relatorio = RelatorioModel.buscar(relatorio_id, usuario_id)
        if not relatorio:
            return None, "Relatório não encontrado."
        return bytes(relatorio["conteudo"]), relatorio["nome"]

    @staticmethod
    def deletar(relatorio_id: int, usuario_id: int) -> tuple:
        try:
            RelatorioModel.deletar(relatorio_id, usuario_id)
            return True, "Relatório removido com sucesso."
        except Exception as e:
            return False, f"Erro ao remover: {str(e)}"