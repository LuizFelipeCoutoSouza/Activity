
import io
import pandas as pd


def carregar_condor(path_ou_bytes) -> tuple[dict, pd.DataFrame]:
    """
    Recebe caminho (str) ou bytes do arquivo Condor.
    Retorna (metadata dict, DataFrame com os dados).
    """
    if isinstance(path_ou_bytes, (str,)):
        with open(path_ou_bytes, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    elif isinstance(path_ou_bytes, bytes):
        raw = path_ou_bytes.decode("utf-8", errors="replace")
    else:
        raw = path_ou_bytes.read().decode("utf-8", errors="replace")

    linhas = raw.splitlines()

    # --- separa cabeçalho dos dados ---
    metadata = {}
    inicio_dados = 0
    for i, linha in enumerate(linhas):
        if linha.startswith("DATE/TIME"):
            inicio_dados = i
            break
        if " : " in linha and not linha.startswith("+") and not linha.startswith("#"):
            chave, valor = linha.split(" : ", 1)
            metadata[chave.strip()] = valor.strip()

    # --- parse da tabela ---
    corpo = "\n".join(linhas[inicio_dados:])
    df = pd.read_csv(io.StringIO(corpo), sep=";", decimal=".", dayfirst=True)


    df.rename(columns={
        "DATE/TIME":     "timestamp",
        "TEMPERATURE":   "temperatura",
        "PIM":           "pim",
        "LIGHT":         "luz",
        "MELANOPIC EDI": "melanopic",
        "STATE":         "estado",
    }, inplace=True)

    # --- converte timestamp ---
    df["timestamp"] = pd.to_datetime(df["timestamp"], dayfirst=True, errors="coerce")
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return metadata, df


def dias_disponiveis(df: pd.DataFrame) -> list[str]:
    return sorted(df["timestamp"].dt.date.astype(str).unique().tolist())


def filtrar_dia(df: pd.DataFrame, data_str: str) -> pd.DataFrame:
    return df[df["timestamp"].dt.date.astype(str) == data_str].copy()
