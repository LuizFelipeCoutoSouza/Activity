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

"""Parsing e geração de arquivos Condor de actigrafia.

Lógica de domínio para o formato de arquivo `.txt` do actígrafo Condor. Não
acessa o banco de dados; é consumido exclusivamente pelo `ArquivoController`.
Oferece o carregamento do arquivo em `(metadata, DataFrame)`, utilitários de
filtragem por dia e a reconstrução do arquivo (`.txt`) ou exportação (`.csv`) a
partir de um DataFrame.
"""

import io
import re

import pandas as pd

_LINHA_DE_DADOS = re.compile(r"^\d{2}/\d{2}/\d{4}")
"""Reconhece o início de uma linha de dados Condor (data no formato dd/mm/aaaa)."""


def carregar_condor(path_ou_bytes) -> tuple[dict, pd.DataFrame]:
    """Carrega um arquivo Condor, separando metadados dos registros.

    Aceita o conteúdo de três formas diferentes e o decodifica como UTF-8
    (substituindo bytes inválidos). Linhas de dados com data/hora inválida,
    timestamps duplicados ou fora de ordem são saneados para não corromper
    cálculos posteriores de frequência e métricas de ritmo.

    Args:
        path_ou_bytes: Caminho do arquivo (str), seu conteúdo (bytes) ou um
            objeto file-like com método `read()`.

    Returns:
        tuple[dict, pandas.DataFrame]: Par `(metadata, df)`. `metadata` mapeia as
        chaves do cabeçalho aos respectivos valores; `df` traz os registros, com
        a coluna `DATE/TIME` já convertida para datetime. Se cabeçalho ou dados
        não forem encontrados, `df` é um DataFrame vazio.
    """
    if isinstance(path_ou_bytes, str):
        with open(path_ou_bytes, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    elif isinstance(path_ou_bytes, bytes):
        raw = path_ou_bytes.decode("utf-8", errors="replace")
    else:
        raw = path_ou_bytes.read().decode("utf-8", errors="replace")

    linhas = raw.splitlines()

    # O arquivo pode trazer mais de uma linha "DATE/TIME;...": uma legenda
    # genérica do formato seguida do cabeçalho real, com número de colunas
    # diferente. Vale a última antes da primeira linha de dados — é ela que casa
    # com as colunas efetivamente presentes nos registros.
    metadata = {}
    cabecalho = None
    inicio_dados = None
    for i, linha in enumerate(linhas):
        if linha.startswith("DATE/TIME"):
            cabecalho = linha
            continue
        if _LINHA_DE_DADOS.match(linha):
            inicio_dados = i
            break
        if " : " in linha and not linha.startswith("+") and not linha.startswith("#"):
            chave, valor = linha.split(" : ", 1)
            metadata[chave.strip()] = valor.strip()

    if cabecalho is None or inicio_dados is None:
        return metadata, pd.DataFrame()

    corpo = "\n".join([cabecalho] + linhas[inicio_dados:])
    df = pd.read_csv(io.StringIO(corpo), sep=";", decimal=".")

    # Datas ilegíveis viram NaT e são removidas: um único NaT no índice corrompe
    # o cálculo de período/frequência do registro e faz as métricas de ritmo do
    # pyActigraphy lançarem KeyError: NaT.
    df["DATE/TIME"] = pd.to_datetime(df["DATE/TIME"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df.dropna(subset=["DATE/TIME"], inplace=True)
    # Timestamps duplicados (falha de gravação do dispositivo) fazem o asfreq()
    # da montagem do BaseRaw falhar com "cannot reindex on an axis with duplicate
    # labels", interrompendo o cálculo de IS/IV/L5/M10.
    df.drop_duplicates(subset=["DATE/TIME"], keep="first", inplace=True)
    df.sort_values("DATE/TIME", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return metadata, df


def dias_disponiveis(df: pd.DataFrame) -> list[str]:
    """Lista as datas distintas presentes no DataFrame, em ordem crescente.

    Args:
        df: DataFrame Condor com a coluna `DATE/TIME`.

    Returns:
        list[str]: Datas únicas no formato ``YYYY-MM-DD``, ordenadas.
    """
    return sorted(df["DATE/TIME"].dt.date.astype(str).unique().tolist())


def filtrar_dia(df: pd.DataFrame, data_str: str) -> pd.DataFrame:
    """Filtra o DataFrame para os registros de um único dia.

    Args:
        df: DataFrame Condor com a coluna `DATE/TIME`.
        data_str: Data alvo no formato ``YYYY-MM-DD``.

    Returns:
        pandas.DataFrame: Cópia com apenas as linhas cuja data corresponde a
        `data_str`.
    """
    return df[df["DATE/TIME"].dt.date.astype(str) == data_str].copy()


def gerar_txt(raw_original: bytes, df: pd.DataFrame) -> bytes:
    """Reconstrói o arquivo Condor (.txt) com os dados de um DataFrame.

    Preserva integralmente o cabeçalho original (incluindo a linha de campos) e
    substitui apenas as linhas de dados pelos valores de `df`, reformatando a
    coluna `DATE/TIME` no padrão Condor e gravando valores ausentes como vazios.

    Args:
        raw_original: Conteúdo binário do arquivo Condor original (fonte do
            cabeçalho e da ordem das colunas).
        df: DataFrame com os registros a escrever.

    Returns:
        bytes: Conteúdo do arquivo `.txt` reconstruído, codificado em UTF-8.
    """
    linhas = raw_original.decode("utf-8", errors="replace").splitlines()

    cabecalho = None
    fim_cabecalho = len(linhas)
    for i, linha in enumerate(linhas):
        if linha.startswith("DATE/TIME"):
            cabecalho = linha
            continue
        if _LINHA_DE_DADOS.match(linha):
            fim_cabecalho = i
            break

    colunas = cabecalho.split(";") if cabecalho else df.columns.tolist()

    linhas_dados = []
    for _, registro in df.iterrows():
        valores = []
        for col in colunas:
            valor = registro.get(col, "")
            if col == "DATE/TIME":
                valor = pd.Timestamp(valor).strftime("%d/%m/%Y %H:%M:%S")
            valores.append("" if pd.isna(valor) else str(valor))
        linhas_dados.append(";".join(valores))

    conteudo = "\n".join(linhas[:fim_cabecalho] + linhas_dados) + "\n"
    return conteudo.encode("utf-8")


def gerar_csv(df: pd.DataFrame) -> bytes:
    """Serializa o DataFrame como CSV simples (colunas e valores).

    Args:
        df: DataFrame a exportar.

    Returns:
        bytes: Conteúdo CSV (sem índice), codificado em UTF-8.
    """
    return df.to_csv(index=False).encode("utf-8")
