import io
import zipfile
from datetime import datetime

import pandas as pd
from model.ArquivoModel import ArquivoModel
from model.condor_parser import (
    carregar_condor      as _carregar_condor,
    dias_disponiveis     as _dias_disponiveis,
    filtrar_dia          as _filtrar_dia,
)


def _detectar_encoding(raw: bytes) -> str:
    if raw.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    for enc in ('utf-8', 'latin-1', 'cp1252'):
        try:
            raw.decode(enc)
            return enc
        except (UnicodeDecodeError, ValueError):
            continue
    return 'binary'


def _extrair_stats(raw: bytes) -> tuple:
    encoding = _detectar_encoding(raw)
    if encoding == 'binary':
        return 0, encoding
    try:
        texto = raw.decode(encoding)
        return len(texto.splitlines()), encoding
    except Exception:
        return 0, 'unknown'


class ArquivoController:

    @staticmethod
    def fazer_upload(usuario_id: int, uploaded_file, descricao: str = "") -> tuple:
        if uploaded_file is None:
            return False, "Nenhum arquivo selecionado."
        if not uploaded_file.name.lower().endswith('.txt'):
            return False, f"'{uploaded_file.name}' não é um arquivo .txt."

        if ArquivoModel.buscar_por_nome(usuario_id, uploaded_file.name):
            return False, f"Já existe um arquivo chamado '{uploaded_file.name}'. Use editar para substituir o conteúdo."

        raw = uploaded_file.read()
        num_linhas, encoding = _extrair_stats(raw)

        try:
            ArquivoModel.salvar(
                usuario_id, uploaded_file.name, descricao.strip(),
                len(raw), num_linhas, encoding, raw,
            )
            return True, f"'{uploaded_file.name}' enviado com sucesso."
        except Exception as e:
            return False, f"Erro ao salvar '{uploaded_file.name}': {str(e)}"

    @staticmethod
    def fazer_upload_em_massa(usuario_id: int, uploaded_files: list, descricao: str = "") -> tuple:
        resultados = []
        for f in uploaded_files:
            ok, msg = ArquivoController.fazer_upload(usuario_id, f, descricao)
            resultados.append((f.name, ok, msg))
        sucesso = sum(1 for _, ok, _ in resultados if ok)
        return resultados, sucesso

    @staticmethod
    def listar(usuario_id: int) -> list:
        return ArquivoModel.listar(usuario_id)

    @staticmethod
    def baixar(arquivo_id: int, usuario_id: int) -> tuple:
        arquivo = ArquivoModel.buscar(arquivo_id, usuario_id)
        if not arquivo:
            return None, "Arquivo não encontrado."
        return bytes(arquivo["conteudo"]), arquivo["nome"]

    @staticmethod
    def atualizar_metadados(arquivo_id: int, usuario_id: int, nome: str, descricao: str) -> tuple:
        nome = nome.strip()
        if not nome:
            return False, "O nome não pode estar vazio."
        if not nome.lower().endswith('.txt'):
            nome += '.txt'

        existente = ArquivoModel.buscar_por_nome(usuario_id, nome)
        if existente and existente['id'] != arquivo_id:
            return False, f"Já existe um arquivo chamado '{nome}'."

        try:
            ArquivoModel.atualizar_metadados(arquivo_id, usuario_id, nome, descricao.strip())
            return True, "Metadados atualizados com sucesso."
        except Exception as e:
            return False, f"Erro ao atualizar: {str(e)}"

    @staticmethod
    def substituir_arquivo(arquivo_id: int, usuario_id: int, nome: str, descricao: str, uploaded_file) -> tuple:
        if uploaded_file is None:
            return False, "Nenhum arquivo selecionado."
        if not uploaded_file.name.lower().endswith('.txt'):
            return False, "O novo arquivo deve ser .txt."

        nome = nome.strip() or uploaded_file.name
        if not nome.lower().endswith('.txt'):
            nome += '.txt'

        existente = ArquivoModel.buscar_por_nome(usuario_id, nome)
        if existente and existente['id'] != arquivo_id:
            return False, f"Já existe um arquivo chamado '{nome}'."

        raw = uploaded_file.read()
        num_linhas, encoding = _extrair_stats(raw)

        try:
            ArquivoModel.substituir_conteudo(
                arquivo_id, usuario_id, nome, descricao.strip(),
                len(raw), num_linhas, encoding, raw,
            )
            return True, "Arquivo substituído com sucesso."
        except Exception as e:
            return False, f"Erro ao substituir: {str(e)}"

    @staticmethod
    def deletar(arquivo_id: int, usuario_id: int) -> tuple:
        try:
            ArquivoModel.deletar(arquivo_id, usuario_id)
            return True, "Arquivo removido com sucesso."
        except Exception as e:
            return False, f"Erro ao remover: {str(e)}"

    # ── Actigrafia ────────────────────────────────────────────────────────────

    @staticmethod
    def carregar_actigrafia(arquivo_id: int, usuario_id: int) -> tuple:
        """Baixa e processa um arquivo Condor. Retorna (metadata, DataFrame) ou ({}, DataFrame vazio)."""
        raw, _ = ArquivoController.baixar(arquivo_id, usuario_id)
        if not raw:
            return {}, pd.DataFrame()
        return _carregar_condor(raw)

    @staticmethod
    def dias_disponiveis(df: pd.DataFrame) -> list:
        """Retorna lista ordenada de datas (YYYY-MM-DD) presentes no DataFrame."""
        return _dias_disponiveis(df)

    @staticmethod
    def filtrar_dia(df: pd.DataFrame, data_str: str) -> pd.DataFrame:
        """Filtra o DataFrame para um único dia."""
        return _filtrar_dia(df, data_str)

    # ── ZIP ───────────────────────────────────────────────────────────────────

    @staticmethod
    def gerar_zip(arquivo_ids: list, usuario_id: int) -> tuple:
        """Compacta os arquivos indicados em um ZIP em memória.

        Retorna (zip_bytes, nome_arquivo, n_incluidos).
        Se nenhum arquivo for encontrado, retorna (None, None, 0).
        """
        buf = io.BytesIO()
        n   = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for arq_id in arquivo_ids:
                raw, nome = ArquivoController.baixar(arq_id, usuario_id)
                if raw:
                    zf.writestr(nome, raw)
                    n += 1
        if n == 0:
            return None, None, 0
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return buf.getvalue(), f"logs_{ts}.zip", n