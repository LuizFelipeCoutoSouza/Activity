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

"""Validação e orquestração de arquivos de actigrafia.

Camada intermediária entre as views e os modelos `ArquivoModel`/`condor_parser`.
Cobre o CRUD dos arquivos `.txt`, a detecção de encoding/contagem de linhas no
upload, o carregamento/filtragem dos dados Condor e a exportação compactada
(`.zip`). As operações com validação seguem o padrão de retorno em tupla.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime

import pandas as pd
from model.arquivo_model import ArquivoModel
from model.condor_parser import (
    carregar_condor      as _carregar_condor,
    dias_disponiveis     as _dias_disponiveis,
    filtrar_dia          as _filtrar_dia,
    gerar_txt            as _gerar_txt,
    gerar_csv            as _gerar_csv,
)


def _detectar_encoding(raw: bytes) -> str:
    """Detecta o encoding provável de um arquivo a partir dos bytes.

    Testa BOM de UTF-8 e, em seguida, decodificações candidatas até uma ter
    sucesso.

    Args:
        raw: Conteúdo binário do arquivo.

    Returns:
        str: Nome do encoding (``utf-8-sig``, ``utf-8``, ``latin-1`` ou
        ``cp1252``); ``binary`` se nenhum candidato decodificar o conteúdo.
    """
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
    """Extrai número de linhas e encoding do conteúdo de um arquivo.

    Args:
        raw: Conteúdo binário do arquivo.

    Returns:
        tuple[int, str]: `(num_linhas, encoding)`. Para conteúdo binário ou
        indecodificável, retorna `(0, encoding)`.
    """
    encoding = _detectar_encoding(raw)
    if encoding == 'binary':
        return 0, encoding
    try:
        texto = raw.decode(encoding)
        return len(texto.splitlines()), encoding
    except Exception:
        return 0, 'unknown'


class ArquivoController:
    """Orquestra o CRUD de arquivos e a análise/exportação de actigrafia."""

    @staticmethod
    def fazer_upload(usuario_id: int, uploaded_file, descricao: str = "") -> tuple:
        """Valida e salva um arquivo `.txt` enviado.

        Rejeita arquivos vazios, com extensão diferente de `.txt` ou com nome já
        em uso pelo usuário.

        Args:
            usuario_id: Id do usuário dono.
            uploaded_file: Objeto de upload do Streamlit (com `.name` e `.read()`).
            descricao: Descrição opcional do arquivo.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
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
        """Envia vários arquivos, reaproveitando `fazer_upload` em cada um.

        Args:
            usuario_id: Id do usuário dono.
            uploaded_files: Lista de objetos de upload.
            descricao: Descrição aplicada a todos os arquivos.

        Returns:
            tuple[list, int]: `(resultados, sucesso)`, onde `resultados` é uma
            lista de `(nome, ok, mensagem)` e `sucesso` é a contagem de envios
            bem-sucedidos.
        """
        resultados = []
        for f in uploaded_files:
            ok, msg = ArquivoController.fazer_upload(usuario_id, f, descricao)
            resultados.append((f.name, ok, msg))
        sucesso = sum(1 for _, ok, _ in resultados if ok)
        return resultados, sucesso

    @staticmethod
    def listar(usuario_id: int) -> list:
        """Lista os metadados dos arquivos de um usuário.

        Args:
            usuario_id: Id do usuário dono.

        Returns:
            list[dict]: Metadados dos arquivos.
        """
        return ArquivoModel.listar(usuario_id)

    @staticmethod
    def baixar(arquivo_id: int, usuario_id: int) -> tuple:
        """Recupera o conteúdo e o nome de um arquivo para download.

        Args:
            arquivo_id: Id do arquivo.
            usuario_id: Id do usuário dono.

        Returns:
            tuple: `(conteudo, nome)` em sucesso; `(None, mensagem)` se o arquivo
            não for encontrado.
        """
        arquivo = ArquivoModel.buscar(arquivo_id, usuario_id)
        if not arquivo:
            return None, "Arquivo não encontrado."
        return bytes(arquivo["conteudo"]), arquivo["nome"]

    @staticmethod
    def atualizar_metadados(arquivo_id: int, usuario_id: int, nome: str, descricao: str) -> tuple:
        """Atualiza nome e descrição de um arquivo.

        Garante a extensão `.txt` no nome e rejeita colisão de nome com outro
        arquivo do mesmo usuário.

        Args:
            arquivo_id: Id do arquivo a atualizar.
            usuario_id: Id do usuário dono.
            nome: Novo nome (recebe `.txt` se faltar).
            descricao: Nova descrição.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
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
        """Substitui o conteúdo de um arquivo, mantendo seu id.

        Recalcula tamanho, linhas e encoding a partir do novo conteúdo. Garante a
        extensão `.txt` e rejeita colisão de nome com outro arquivo do usuário.

        Args:
            arquivo_id: Id do arquivo a substituir.
            usuario_id: Id do usuário dono.
            nome: Novo nome; se vazio, usa o nome do arquivo enviado.
            descricao: Nova descrição.
            uploaded_file: Objeto de upload com o novo conteúdo `.txt`.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
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
        """Remove um arquivo do usuário.

        Args:
            arquivo_id: Id do arquivo a remover.
            usuario_id: Id do usuário dono.

        Returns:
            tuple[bool, str]: `(sucesso, mensagem)`.
        """
        try:
            ArquivoModel.deletar(arquivo_id, usuario_id)
            return True, "Arquivo removido com sucesso."
        except Exception as e:
            return False, f"Erro ao remover: {str(e)}"

    # ── Actigrafia ────────────────────────────────────────────────────────────

    @staticmethod
    def carregar_actigrafia(arquivo_id: int, usuario_id: int) -> tuple:
        """Baixa e processa um arquivo Condor para análise.

        Args:
            arquivo_id: Id do arquivo.
            usuario_id: Id do usuário dono.

        Returns:
            tuple[dict, pandas.DataFrame]: `(metadata, df)` do parser Condor; ou
            `({}, DataFrame vazio)` se o arquivo não for encontrado.
        """
        raw, _ = ArquivoController.baixar(arquivo_id, usuario_id)
        if not raw:
            return {}, pd.DataFrame()
        return _carregar_condor(raw)

    @staticmethod
    def dias_disponiveis(df: pd.DataFrame) -> list:
        """Lista as datas distintas presentes no DataFrame.

        Args:
            df: DataFrame Condor.

        Returns:
            list[str]: Datas únicas (``YYYY-MM-DD``) em ordem crescente.
        """
        return _dias_disponiveis(df)

    @staticmethod
    def filtrar_dia(df: pd.DataFrame, data_str: str) -> pd.DataFrame:
        """Filtra o DataFrame para os registros de um único dia.

        Args:
            df: DataFrame Condor.
            data_str: Data alvo no formato ``YYYY-MM-DD``.

        Returns:
            pandas.DataFrame: Cópia apenas com as linhas do dia indicado.
        """
        return _filtrar_dia(df, data_str)

    @staticmethod
    def exportar_dados(
        arquivo_id: int, usuario_id: int, df: pd.DataFrame,
        incluir_dados: bool = True, extras: dict[str, bytes] | None = None,
    ) -> tuple:
        """Monta um ZIP com os dados exportados e/ou arquivos extras.

        Quando `incluir_dados`, adiciona o `.txt` (formato Condor reconstruído a
        partir de `df`) e o `.csv`. Os itens de `extras` (ex.: PNGs de gráficos)
        são sempre adicionados.

        Args:
            arquivo_id: Id do arquivo de origem.
            usuario_id: Id do usuário dono.
            df: DataFrame com os dados a exportar.
            incluir_dados: Se True, inclui os arquivos `.txt` e `.csv`.
            extras: Mapa `nome_no_zip -> conteúdo` de arquivos adicionais.

        Returns:
            tuple: `(zip_bytes, nome_arquivo)` em sucesso; `(None, None)` se o
            arquivo de origem não for encontrado.
        """
        raw, nome = ArquivoController.baixar(arquivo_id, usuario_id)
        if not raw:
            return None, None

        nome_base = nome.rsplit(".", 1)[0]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if incluir_dados:
                zf.writestr(f"{nome_base}.txt", _gerar_txt(raw, df))
                zf.writestr(f"{nome_base}.csv", _gerar_csv(df))
            for nome_extra, conteudo in (extras or {}).items():
                zf.writestr(nome_extra, conteudo)
        return buf.getvalue(), f"{nome_base}_exportado.zip"

    # ── ZIP ───────────────────────────────────────────────────────────────────

    @staticmethod
    def gerar_zip(arquivo_ids: list, usuario_id: int) -> tuple:
        """Compacta vários arquivos do usuário em um ZIP em memória.

        Args:
            arquivo_ids: Ids dos arquivos a incluir.
            usuario_id: Id do usuário dono.

        Returns:
            tuple: `(zip_bytes, nome_arquivo, n_incluidos)` em sucesso, com nome
            baseado em timestamp; `(None, None, 0)` se nenhum arquivo for
            encontrado.
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