import io
import re

import pandas as pd

_LINHA_DE_DADOS = re.compile(r"^\d{2}/\d{2}/\d{4}")


def carregar_condor(path_ou_bytes) -> tuple[dict, pd.DataFrame]:
    """
    Recebe caminho (str) ou bytes do arquivo Condor.
    Retorna (metadata dict, DataFrame com os dados).
    """
    if isinstance(path_ou_bytes, str):
        with open(path_ou_bytes, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    elif isinstance(path_ou_bytes, bytes):
        raw = path_ou_bytes.decode("utf-8", errors="replace")
    else:
        raw = path_ou_bytes.read().decode("utf-8", errors="replace")

    linhas = raw.splitlines()

    # --- separa cabeçalho dos dados ---
    # O arquivo pode trazer mais de uma linha "DATE/TIME;...": uma legenda
    # genérica do formato seguida do cabeçalho real, com número de colunas
    # diferente. A que vale é a última antes da primeira linha de dados —
    # é ela que casa com as colunas efetivamente presentes nos registros.
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

    # --- parse da tabela ---
    corpo = "\n".join([cabecalho] + linhas[inicio_dados:])
    df = pd.read_csv(io.StringIO(corpo), sep=";", decimal=".")

    # --- converte timestamp ---
    # linhas com data/hora ilegível viram NaT e são descartadas: um único
    # NaT no índice corrompe o cálculo de período/frequência do registro
    # (e, com isso, as métricas de ritmo do pyActigraphy, que passam a
    # lançar KeyError: NaT).
    df["DATE/TIME"] = pd.to_datetime(df["DATE/TIME"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df.dropna(subset=["DATE/TIME"], inplace=True)
    # timestamps duplicados (falha de gravação do dispositivo) fazem o
    # asfreq() usado para montar o BaseRaw falhar com "cannot reindex on an
    # axis with duplicate labels", interrompendo o cálculo de IS/IV/L5/M10.
    df.drop_duplicates(subset=["DATE/TIME"], keep="first", inplace=True)
    df.sort_values("DATE/TIME", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return metadata, df


def dias_disponiveis(df: pd.DataFrame) -> list[str]:
    return sorted(df["DATE/TIME"].dt.date.astype(str).unique().tolist())


def filtrar_dia(df: pd.DataFrame, data_str: str) -> pd.DataFrame:
    return df[df["DATE/TIME"].dt.date.astype(str) == data_str].copy()


def gerar_txt(raw_original: bytes, df: pd.DataFrame) -> bytes:
    """
    Reconstrói o arquivo Condor (.txt), preservando todas as linhas de
    cabeçalho (incluindo a linha de campos) e substituindo as linhas de
    dados pelos valores de df.
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
    """Gera um CSV contendo apenas os campos (colunas) e seus valores."""
    return df.to_csv(index=False).encode("utf-8")
