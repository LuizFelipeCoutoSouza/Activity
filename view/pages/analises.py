
import datetime as _dt
from typing import cast

import pandas as pd
import plotly.graph_objs as go
from pyActigraphy.io import BaseRaw
import streamlit as st
from controller.arquivo_controller import ArquivoController
from controller.relatorio_controller import RelatorioController
from view.ui import render_toast, set_toast, get_usuario_id


COR_LINHA = "#234cbe"
COR_LUZ = "#ffb433"
COR_TEMPERATURA = "#c43903"
COR_LEGENDA = "black"
COR_SOMBRA_NOITE = "rgba(25, 35, 90, 0.12)"
COR_SOMBRA_EVENTO = "rgba(34, 139, 34, 0.18)"

# Paleta de cores para comparação entre pacientes (até 5)
_CORES_COMPARACAO = {
    0: {
        "atividade": "#234cbe",
        "temperatura": "#5d7df0",
        "luz": "#9bb5ff",
    },
    1: {
        "atividade": "#e84545",
        "temperatura": "#ff7a7a",
        "luz": "#ffb3b3",
    },
    2: {
        "atividade": "#2eb872",
        "temperatura": "#60d89b",
        "luz": "#9ff0c8",
    },
    3: {
        "atividade": "#f5a623",
        "temperatura": "#ffc55f",
        "luz": "#ffe09d",
    },
    4: {
        "atividade": "#9b59b6",
        "temperatura": "#bc7dd6",
        "luz": "#ddbef0",
    },
}
MODOS_ATIVIDADE = ["PIM", "TAT", "ZCM"]

_DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

_PERIODOS_DIA = {
    "Dia inteiro":      (0, 24),
    "Manhã (06h–12h)":  (6, 12),
    "Tarde (12h–18h)":  (12, 18),
    "Noite (18h–24h)":  (18, 24),
}

_DURACOES_MASCARA_H  = list(range(0, 13, 2))
_DURACOES_DESCARTE_H = list(range(0, 13, 2))

_PERIODOS_FIXOS = [
    (1,  "1 dia",   "1D"),
    (3,  "3 dias",  "3D"),
    (7,  "7 dias",  "7D"),
    (14, "14 dias", "14D"),
    (30, "30 dias", "30D"),
]

_LARGURA_EIXO_EXTRA = 0.08

_ERROS_METRICA_RITMO = (KeyError, ValueError, ZeroDivisionError)
_AVISO_DADOS_INSUFICIENTES = (
    "Não foi possível calcular esta métrica para o registro selecionado — "
    "o pyActigraphy exige pelo menos 24h de dados contínuos para estimar o ritmo de repouso-atividade."
)


# ── Cache de I/O ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def _carregar_actigrafia(arquivo_id: int, usuario_id: int) -> tuple:
    return ArquivoController.carregar_actigrafia(arquivo_id, usuario_id)


@st.cache_data(ttl=120, show_spinner=False)
def _gerar_export_zip(arquivo_id: int, usuario_id: int, df: pd.DataFrame) -> tuple:
    return ArquivoController.exportar_dados(arquivo_id, usuario_id, df)


# ── Construção do objeto BaseRaw ──────────────────────────────────────────────

def _construir_raw(nome: str, df: pd.DataFrame, coluna: str) -> BaseRaw:
    serie = pd.Series(df[coluna].to_numpy(), index=pd.DatetimeIndex(df["DATE/TIME"]), name="Activity")
    frequencia = pd.Timedelta(serie.index.to_series().diff().median())
    serie = serie.asfreq(frequencia)
    return BaseRaw(
        name=nome, uuid=nome, format="CONDOR", axial_mode=None,
        start_time=serie.index[0], period=serie.index[-1] - serie.index[0],
        frequency=frequencia, data=serie, light=None,
    )


@st.cache_data(ttl=120, show_spinner=False)
def _construir_raw_cached(nome: str, df: pd.DataFrame, coluna: str) -> BaseRaw:
    return _construir_raw(nome, df, coluna)


# ── Cálculo cacheado de métricas (pesado) ─────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _computar_metricas_globais(
    df: pd.DataFrame, nome: str, coluna: str,
    freq: str, limiar: int, mask_h: int | None,
) -> dict | None:
    raw = _construir_raw_cached(nome, df, coluna)
    if mask_h is not None:
        raw.create_inactivity_mask(f"{mask_h}h")
        raw.mask_inactivity = True
    try:
        return {
            "is":  float(raw.IS(freq=freq, threshold=limiar)),
            "iv":  float(raw.IV(freq=freq, threshold=limiar)),
            "l5":  float(raw.L5(threshold=limiar)),
            "m10": float(raw.M10(threshold=limiar)),
        }
    except _ERROS_METRICA_RITMO:
        return None


@st.cache_data(ttl=120, show_spinner=False)
def _computar_metricas_periodo(
    df: pd.DataFrame, nome: str, coluna: str,
    freq: str, limiar: int, mask_h: int | None, periodo: str,
) -> pd.DataFrame | None:
    raw = _construir_raw_cached(nome, df, coluna)
    if mask_h is not None:
        raw.create_inactivity_mask(f"{mask_h}h")
        raw.mask_inactivity = True
    try:
        vals_is  = raw.ISp(period=periodo, freq=freq, threshold=limiar)
        vals_iv  = raw.IVp(period=periodo, freq=freq, threshold=limiar)
        vals_l5  = raw.L5p(period=periodo, threshold=limiar)
        vals_m10 = raw.M10p(period=periodo, threshold=limiar)
        n = max(len(vals_is), len(vals_iv), len(vals_l5), len(vals_m10))
        return pd.DataFrame(
            {"IS": vals_is, "IV": vals_iv, "L5": vals_l5, "M10": vals_m10},
            index=[f"Período {i + 1}" for i in range(n)],
        )
    except _ERROS_METRICA_RITMO:
        return None


# ── Helpers de sombreamento ───────────────────────────────────────────────────

def _sombrear_periodo_noturno(
    fig: go.Figure, inicio: pd.Timestamp,
    row: int | str = "all", col: int | str = "all",
) -> None:
    for ini, fim in (
        (inicio,                              inicio + pd.Timedelta(hours=6)),
        (inicio + pd.Timedelta(hours=18),     inicio + pd.Timedelta(days=1)),
    ):
        fig.add_vrect(x0=ini, x1=fim, fillcolor=COR_SOMBRA_NOITE, line_width=0, layer="below", row=row, col=col)


def _intervalos_marcados(mascara: pd.Series) -> list[tuple]:
    intervalos: list[tuple] = []
    em_intervalo = False
    inicio = anterior = None
    for ts, valor in mascara.items():
        if valor and not em_intervalo:
            inicio, em_intervalo = ts, True
        elif not valor and em_intervalo:
            intervalos.append((inicio, anterior))
            em_intervalo = False
        anterior = ts
    if em_intervalo:
        intervalos.append((inicio, anterior))
    return intervalos


def _sombrear_eventos(
    fig: go.Figure, serie_evento: pd.Series, dia: str,
    row: int | str = "all", col: int | str = "all",
) -> None:
    try:
        fatia = serie_evento.loc[dia]
    except KeyError:
        return
    marcado = fatia.fillna(0) != 0
    for ini, fim in _intervalos_marcados(marcado):
        fig.add_vrect(x0=ini, x1=fim, fillcolor=COR_SOMBRA_EVENTO, line_width=0, layer="below", row=row, col=col)


# ── Helpers de rótulo ─────────────────────────────────────────────────────────

def _rotulo_dia(numero_dia: int, dia: str) -> str:
    ts = pd.Timestamp(dia)
    idx = int(ts.weekday())
    dia_semana = _DIAS_SEMANA[idx] + ("-feira" if idx < 5 else "")
    return f"Dia {numero_dia} — {ts.strftime('%d/%m/%Y')} · {dia_semana}"


def _rotulo_genero(valor: str | None) -> str:
    if not valor:
        return "—"
    inicial = valor.strip().upper()[:1]
    if inicial == "M":
        return "MASCULINO"
    if inicial == "F":
        return "FEMININO"
    return valor.strip().upper()


def _coluna_numerica_utilizavel(df: pd.DataFrame, nome_coluna: str) -> pd.Series | None:
    if nome_coluna not in df.columns:
        return None
    valores = pd.to_numeric(df[nome_coluna], errors="coerce")
    return valores if valores.notna().any() else None


# ── Filtro global baseado em luz ──────────────────────────────────────────────

def _aplicar_filtro_global_luz(
    df: pd.DataFrame,
    faixa_filtro_luz: tuple[float, float],
) -> pd.DataFrame:
    """
    Remove do DataFrame todas as linhas cujo valor LIGHT está fora da faixa
    especificada. Retorna um novo DataFrame (não modifica o original).
    Usado quando o filtro global por luz está ativado — afeta gráficos,
    métricas e exportação.
    """
    if "LIGHT" not in df.columns:
        return df
    luz = pd.to_numeric(df["LIGHT"], errors="coerce")
    mascara = luz.between(faixa_filtro_luz[0], faixa_filtro_luz[1], inclusive="both")
    return df[mascara].copy()


# ── Preparação dos dados para exportação ──────────────────────────────────────

def _preparar_df_exportacao(
    df: pd.DataFrame,
    dt_index: pd.DatetimeIndex,
    modos_disponiveis: list[str],
    modo_atividade: str,
    mostrar_atividade: bool,
    escala_atividade: tuple[float, float],
    raw: BaseRaw,
    mask_h: int | None,
    mostrar_luz: bool,
    escala_luz: tuple[float, float] | None,
    mostrar_temperatura: bool,
    escala_temperatura: tuple[float, float] | None,
    dias_exibidos: list[str],
    hora_inicio: int,
    hora_fim: int,
) -> pd.DataFrame:
    """
    Copia df e zera os valores de atividade/luz/temperatura que não
    correspondem aos sinais e filtros selecionados em "Opções de exibição"
    e "Filtrar dias exibidos" — preserva todas as colunas e linhas.
    """
    df = df.copy()

    def _zerar_fora_da_faixa(nome_coluna: str, faixa: tuple[float, float] | None) -> None:
        if faixa is None:
            return
        valores = pd.to_numeric(df[nome_coluna], errors="coerce")
        fora = (valores < faixa[0]) | (valores > faixa[1])
        df.loc[fora.fillna(False).to_numpy(), nome_coluna] = 0

    # atividade: mantém apenas o modo selecionado, se exibido
    for coluna in modos_disponiveis:
        if coluna not in df.columns:
            continue
        if coluna != modo_atividade or not mostrar_atividade:
            df[coluna] = 0

    if mostrar_atividade and modo_atividade in df.columns:
        _zerar_fora_da_faixa(modo_atividade, escala_atividade)
        if mask_h is not None:
            # períodos mascarados (sensor removido) viram dado ausente —
            # zerar não teria efeito, pois o mascaramento já incide sobre
            # trechos de atividade igual a zero
            df[modo_atividade] = df[modo_atividade].astype(float)
            mascarado = raw.data.reindex(dt_index).isna().to_numpy()
            df.loc[mascarado, modo_atividade] = float("nan")

    if "LIGHT" in df.columns:
        if not mostrar_luz:
            df["LIGHT"] = 0
        else:
            _zerar_fora_da_faixa("LIGHT", escala_luz)

    if "TEMPERATURE" in df.columns:
        if not mostrar_temperatura:
            df["TEMPERATURE"] = 0
        else:
            _zerar_fora_da_faixa("TEMPERATURE", escala_temperatura)

    # filtro de dias/período exibidos: zera os sinais fora da seleção
    dia_str = pd.Series(dt_index.date).astype(str)
    hora = dt_index.hour + dt_index.minute / 60
    fora_do_filtro = ~(dia_str.isin(dias_exibidos).to_numpy() & (hora >= hora_inicio) & (hora < hora_fim))
    colunas_sinais = [c for c in (*modos_disponiveis, "LIGHT", "TEMPERATURE") if c in df.columns]
    if colunas_sinais:
        df.loc[fora_do_filtro, colunas_sinais] = 0

    return df


# ── Gráfico diário cacheado ───────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _grafico_combinado_dia(
    dia: str,
    numero_dia: int,
    serie_atividade: pd.Series,
    escala_atividade: tuple[float, float],
    rotulo_atividade: str,
    cor_atividade: str = COR_LINHA,
    mostrar_atividade: bool = True,
    serie_luz: pd.Series | None = None,
    serie_temp: pd.Series | None = None,
    serie_evento: pd.Series | None = None,
    escala_luz: tuple[float, float] | None = None,
    escala_temperatura: tuple[float, float] | None = None,
    hora_inicio: int = 0,
    hora_fim: int = 24,
) -> go.Figure:
    inicio_dia = pd.Timestamp(dia)
    inicio = inicio_dia + pd.Timedelta(hours=hora_inicio)
    fim    = inicio_dia + pd.Timedelta(hours=hora_fim) - pd.Timedelta(seconds=1)

    serie_atividade = serie_atividade.loc[inicio:fim]

    extras = [
        (rotulo, cor, serie, faixa)
        for rotulo, cor, serie, faixa in (
            ("Luz (Lux)",        COR_LUZ,         serie_luz,  escala_luz),
            ("Temperatura (°C)", COR_TEMPERATURA, serie_temp, escala_temperatura),
        )
        if serie is not None
    ]

    fim_dominio_x = 1 - _LARGURA_EIXO_EXTRA * len(extras)

    fig = go.Figure()
    if mostrar_atividade:
        fig.add_trace(go.Scatter(
            x=serie_atividade.index, y=serie_atividade.values, mode="lines",
            name=rotulo_atividade, line=dict(color=cor_atividade),
        ))

    layout = dict(
        title=dict(text=_rotulo_dia(numero_dia, dia), x=0.01, xanchor="left", font=dict(size=14, color=COR_LEGENDA)),
        xaxis=dict(title="Hora", domain=[0, fim_dominio_x], range=[inicio, fim], tickformat="%H:%M"),
        yaxis=dict(
            title=dict(text=rotulo_atividade, font=dict(color=cor_atividade)),
            tickfont=dict(color=cor_atividade),
            range=escala_atividade,
        ),
        height=340,
        margin=dict(l=0, r=0, t=60, b=0),
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(255, 255, 255, 0.75)",
            bordercolor="rgba(0, 0, 0, 0.15)", borderwidth=1,
            font=dict(size=11, color=COR_LEGENDA),
        ),
    )

    for i, (rotulo, cor, serie, faixa) in enumerate(extras):
        indice_eixo = i + 2
        eixo_id = f"y{indice_eixo}"
        fatia = serie.loc[inicio:fim]
        fig.add_trace(go.Scatter(
            x=fatia.index, y=fatia.values, mode="lines",
            name=rotulo, line=dict(color=cor, dash="dot"), yaxis=eixo_id,
        ))
        eixo: dict = dict(
            title=dict(text=rotulo, font=dict(color=cor)),
            tickfont=dict(color=cor),
            range=faixa, overlaying="y", side="right",
        )
        if i > 0:
            eixo["anchor"]   = "free"
            eixo["position"] = fim_dominio_x + _LARGURA_EIXO_EXTRA * i
        layout[f"yaxis{indice_eixo}"] = eixo

    fig.update_layout(**layout)
    _sombrear_periodo_noturno(fig, inicio_dia)
    if serie_evento is not None:
        _sombrear_eventos(fig, serie_evento, dia)
    return fig


# ── Exibição de métricas ──────────────────────────────────────────────────────

def _metricas_ritmo(
    df: pd.DataFrame,
    nome: str,
    coluna: str,
    titulo: str = "Ritmo de repouso-atividade",
    freq: str = "1H",
    limiar: int = 4,
    usar_periodo: bool = False,
    periodo: str = "7D",
    mask_h: int | None = None,
) -> None:
    st.subheader(titulo)
    if usar_periodo:
        resultado = _computar_metricas_periodo(df, nome, coluna, freq, limiar, mask_h, periodo)
        if resultado is None:
            st.info(_AVISO_DADOS_INSUFICIENTES)
        else:
            st.dataframe(resultado.style.format("{:.3f}"), use_container_width=True)
    else:
        resultado = _computar_metricas_globais(df, nome, coluna, freq, limiar, mask_h)
        if resultado is None:
            st.info(_AVISO_DADOS_INSUFICIENTES)
        else:
            col_is, col_iv, col_l5, col_m10 = st.columns(4)
            col_is.metric("IS — geral",  f"{resultado['is']:.3f}",
                          help="Estabilidade interdiária: o quanto o padrão de repouso-atividade se repete de um dia para o outro.")
            col_iv.metric("IV — geral",  f"{resultado['iv']:.3f}",
                          help="Variabilidade intradiária: o quanto a atividade se fragmenta ao longo do dia.")
            col_l5.metric("L5 — geral",  f"{resultado['l5']:.3f}",
                          help="Atividade média durante as 5 horas menos ativas do dia (média entre todos os dias do registro).")
            col_m10.metric("M10 — geral", f"{resultado['m10']:.3f}",
                           help="Atividade média durante as 10 horas mais ativas do dia (média entre todos os dias do registro).")


# ── Callback de exportação ─────────────────────────────────────────────────────

def _salvar_relatorio(usuario_id: int, nome_origem: str, zip_nome: str, zip_bytes: bytes) -> None:
    RelatorioController.salvar(usuario_id, zip_nome, nome_origem, zip_bytes)
    set_toast("Relatório exportado e salvo em Exportar relatório.")


# ══════════════════════════════════════════════════════════════════════════════
# ABA DE COMPARAÇÃO — funções auxiliares
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=120, show_spinner=False)
def _carregar_varios_arquivos(
    arquivo_ids: tuple[int, ...], usuario_id: int
) -> list[tuple[dict, pd.DataFrame]]:
    """
    Carrega múltiplos arquivos de actigrafia preservando o cache por tupla de IDs.
    Retorna lista de (metadata, DataFrame) na mesma ordem dos IDs fornecidos.
    """
    return [_carregar_actigrafia(arq_id, usuario_id) for arq_id in arquivo_ids]


def _alinhar_dia_relativo(df: pd.DataFrame, dia_relativo: int) -> pd.DataFrame | None:
    """
    Retorna o subconjunto do DataFrame correspondente ao dia relativo (1-based).
    Exemplo: dia_relativo=1 → primeiro dia do registro.
    Retorna None se o dia não existir no registro.
    """
    dias = sorted(df["DATE/TIME"].dt.date.unique())
    if dia_relativo < 1 or dia_relativo > len(dias):
        return None
    data_alvo = dias[dia_relativo - 1]
    fatia = df[df["DATE/TIME"].dt.date == data_alvo].copy()
    # Normaliza o índice temporal para 00:00 do dia relativo (1970-01-01 + dia_relativo-1)
    # Isso alinha os eixos X de pacientes com datas reais diferentes.
    data_base = pd.Timestamp("1970-01-01") + pd.Timedelta(days=dia_relativo - 1)
    delta = data_base - pd.Timestamp(data_alvo)
    fatia = fatia.copy()
    fatia["DATE/TIME"] = fatia["DATE/TIME"] + delta
    return fatia


@st.cache_data(ttl=120, show_spinner=False)
def _estatisticas_comparacao(
    df: pd.DataFrame,
    nome_arquivo: str,
    modo_atividade: str,
    dia_ini: int,
    dia_fim: int,
) -> dict:
    """
    Calcula média, mediana e desvio padrão de atividade, luz e temperatura
    para o intervalo de dias relativos [dia_ini, dia_fim].
    """
    dias = sorted(df["DATE/TIME"].dt.date.unique())
    dias_sel = dias[dia_ini - 1 : dia_fim]
    df_sel = df[df["DATE/TIME"].dt.date.isin(dias_sel)]

    def _stats(serie: pd.Series | None) -> dict:
        if serie is None or serie.dropna().empty:
            return {"Média": "—", "Mediana": "—", "Desvio padrão": "—"}
        s = pd.to_numeric(serie, errors="coerce").dropna()
        return {
            "Média":         f"{s.mean():.2f}",
            "Mediana":       f"{s.median():.2f}",
            "Desvio padrão": f"{s.std():.2f}",
        }

    ativ = _coluna_numerica_utilizavel(df_sel, modo_atividade) if modo_atividade in df_sel.columns else None
    luz  = _coluna_numerica_utilizavel(df_sel, "LIGHT")
    temp = _coluna_numerica_utilizavel(df_sel, "TEMPERATURE")

    return {
        "arquivo":    nome_arquivo,
        "atividade":  _stats(ativ),
        "luz":        _stats(luz),
        "temperatura": _stats(temp),
    }


def _grafico_comparacao_dia(
    dia_relativo: int,
    pacientes: list[dict],  # lista de {nome, numero, df, cores}
    modo_atividade: str,
    mostrar_atividade: bool,
    mostrar_luz: bool,
    mostrar_temperatura: bool,
) -> go.Figure:
    """
    Gera um gráfico comparativo para um dia relativo, sobrepondo os sinais de
    todos os pacientes. O eixo X representa as 24h normalizadas.
    """
    # Data base de referência (eixo X)
    data_base = pd.Timestamp("1970-01-01") + pd.Timedelta(days=dia_relativo - 1)
    inicio = data_base
    fim    = data_base + pd.Timedelta(hours=24) - pd.Timedelta(seconds=1)

    atividade_traces: list[tuple[pd.DatetimeIndex, pd.Series, int, dict]] = []
    luz_traces: list[tuple[pd.DatetimeIndex, pd.Series, int, dict]] = []
    temp_traces: list[tuple[pd.DatetimeIndex, pd.Series, int, dict]] = []

    for pac in pacientes:
        nome = pac["nome"]
        numero = pac["numero"]
        df   = pac["df"]
        cores = pac["cores"]
        fatia = _alinhar_dia_relativo(df, dia_relativo)
        if fatia is None or fatia.empty:
            continue
        dt_idx = pd.DatetimeIndex(fatia["DATE/TIME"])
        fatia_range = fatia[(fatia["DATE/TIME"] >= inicio) & (fatia["DATE/TIME"] <= fim)]
        if fatia_range.empty:
            continue

        # Atividade
        if mostrar_atividade and modo_atividade in fatia_range.columns:
            ativ = pd.to_numeric(fatia_range[modo_atividade], errors="coerce")
            if ativ.notna().any():
                atividade_traces.append((fatia_range["DATE/TIME"], ativ, numero, cores))

        # Luz
        if mostrar_luz and "LIGHT" in fatia_range.columns:
            luz = pd.to_numeric(fatia_range["LIGHT"], errors="coerce")
            if luz.notna().any():
                luz_traces.append((fatia_range["DATE/TIME"], luz, numero, cores))

        # Temperatura
        if mostrar_temperatura and "TEMPERATURE" in fatia_range.columns:
            temp = pd.to_numeric(fatia_range["TEMPERATURE"], errors="coerce")
            if temp.notna().any():
                temp_traces.append((fatia_range["DATE/TIME"], temp, numero, cores))

    tem_luz_algum = bool(luz_traces)
    tem_temp_algum = bool(temp_traces)

    extras_presentes = int(tem_luz_algum) + int(tem_temp_algum)
    fim_dominio_x = 1 - _LARGURA_EIXO_EXTRA * extras_presentes

    fig = go.Figure()

    for x_vals, y_vals, numero, cores in atividade_traces:
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals.values, mode="lines",
            name=f"Atividade - Paciente {numero}",
            line=dict(color=cores["atividade"]),
        ))

    for x_vals, y_vals, numero, cores in luz_traces:
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals.values, mode="lines",
            name=f"Luz - Paciente {numero}",
            line=dict(color=cores["luz"], dash="dot"),
            yaxis="y2",
        ))

    temperatura_axis = "y3" if tem_luz_algum else "y2"
    for x_vals, y_vals, numero, cores in temp_traces:
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals.values, mode="lines",
            name=f"Temperatura - Paciente {numero}",
            line=dict(color=cores["temperatura"], dash="dashdot"),
            yaxis=temperatura_axis,
        ))

    layout: dict = dict(
        title=dict(
            text=f"Dia relativo {dia_relativo}",
            x=0.01, xanchor="left", font=dict(size=14, color=COR_LEGENDA),
        ),
        xaxis=dict(
            title="Hora", domain=[0, fim_dominio_x],
            range=[inicio, fim], tickformat="%H:%M",
        ),
        yaxis=dict(
            title=dict(text=modo_atividade, font=dict(color=COR_LEGENDA)),
            tickfont=dict(color=COR_LEGENDA),
        ),
        height=400,
        margin=dict(l=0, r=0, t=60, b=0),
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(255, 255, 255, 0.75)",
            bordercolor="rgba(0, 0, 0, 0.15)", borderwidth=1,
            font=dict(size=11, color=COR_LEGENDA),
        ),
    )

    # Eixo Y2 para o primeiro sinal extra exibido
    if tem_luz_algum or tem_temp_algum:
        layout["yaxis2"] = dict(
            title=dict(
                text="Luz (Lux)" if tem_luz_algum else "Temperatura (°C)",
                font=dict(color=COR_LUZ if tem_luz_algum else COR_TEMPERATURA),
            ),
            tickfont=dict(color=COR_LUZ if tem_luz_algum else COR_TEMPERATURA),
            overlaying="y", side="right",
        )

    # Eixo Y3 para o segundo sinal extra exibido
    if tem_luz_algum and tem_temp_algum:
        eixo_temp: dict = dict(
            title=dict(text="Temperatura (°C)", font=dict(color=COR_TEMPERATURA)),
            tickfont=dict(color=COR_TEMPERATURA),
            overlaying="y", side="right",
        )
        eixo_temp["anchor"] = "free"
        eixo_temp["position"] = fim_dominio_x + _LARGURA_EIXO_EXTRA
        layout["yaxis3"] = eixo_temp

    fig.update_layout(**layout)
    _sombrear_periodo_noturno(fig, data_base)
    return fig


def _tabela_resumo_comparacao(
    pacientes: list[dict],
    modo_atividade: str,
    dia_ini: int,
    dia_fim: int,
) -> None:
    """
    Exibe tabela de resumo estatístico com uma linha por paciente e colunas
    agrupadas por sinal (atividade, luz e temperatura).
    """
    linhas = []
    for pac in pacientes:
        stats = _estatisticas_comparacao(
            pac["df"], pac["nome"], modo_atividade, dia_ini, dia_fim
        )
        atividade = stats["atividade"]
        luz = stats["luz"]
        temperatura = stats["temperatura"]
        linhas.append({
            "Paciente": f"Paciente {pac['numero']}",
            f"Atividade Média ({modo_atividade})": atividade["Média"],
            f"Atividade Mediana ({modo_atividade})": atividade["Mediana"],
            f"Atividade DesvioPadrão ({modo_atividade})": atividade["Desvio padrão"],
            "Luz Média (Lux)": luz["Média"],
            "Luz Mediana (Lux)": luz["Mediana"],
            "Luz DesvioPadrão (Lux)": luz["Desvio padrão"],
            "Temp Média (°C)": temperatura["Média"],
            "Temp Mediana (°C)": temperatura["Mediana"],
            "Temp DesvioPadrão(°C)": temperatura["Desvio padrão"],
        })

    if linhas:
        tabela = pd.DataFrame(linhas).sort_values("Paciente")
        st.dataframe(tabela, use_container_width=True, hide_index=True)


# ── Aba de comparação entre pacientes ────────────────────────────────────────

def _aba_comparacao(usuario_id: int, arquivos: list) -> None:
    """
    Renderiza a aba de comparação entre pacientes.
    Permite selecionar até 5 arquivos, escolher o modo de atividade,
    definir um intervalo de dias relativos e visualizar gráficos sobrepostos.
    """
    st.subheader("Comparação entre pacientes")
    st.caption(
        "Selecione de 2 a 5 arquivos para comparar. A comparação usa **dias relativos** — "
        "o Dia 1 de cada paciente é o primeiro dia do respectivo registro, "
        "independente da data real."
    )

    opcoes = {arq["nome"]: arq["id"] for arq in arquivos}
    nomes_selecionados: list[str] = st.multiselect(
        "Arquivos para comparar",
        options=list(opcoes.keys()),
        max_selections=5,
        placeholder="Selecione de 2 a 5 arquivos...",
    )

    if nomes_selecionados:
        legenda_pacientes = "\n".join(
            f"- Paciente {numero}: {nome}"
            for numero, nome in enumerate(nomes_selecionados, start=1)
        )
        st.info(f"**Identificação dos pacientes**\n{legenda_pacientes}")

    if len(nomes_selecionados) < 2:
        st.info("Selecione pelo menos 2 arquivos para iniciar a comparação.")
        return
    if len(nomes_selecionados) > 5:
        st.warning("Selecione no máximo 5 arquivos.")
        return

    # Carrega todos os arquivos selecionados (com cache)
    ids_selecionados = tuple(opcoes[n] for n in nomes_selecionados)
    with st.spinner("Carregando arquivos..."):
        dados_carregados = _carregar_varios_arquivos(ids_selecionados, usuario_id)

    # Valida e monta lista de pacientes válidos
    pacientes_validos: list[dict] = []
    for numero, nome, (metadata, df) in zip(
        range(1, len(nomes_selecionados) + 1),
        nomes_selecionados,
        dados_carregados,
    ):
        if df.empty:
            st.warning(f"Não foi possível processar **{nome}** — arquivo ignorado.")
            continue
        pacientes_validos.append({"nome": nome, "numero": numero, "metadata": metadata, "df": df})

    if len(pacientes_validos) < 2:
        st.error("Pelo menos 2 arquivos válidos são necessários para a comparação.")
        return

    # Atribui cores a cada paciente
    for i, pac in enumerate(pacientes_validos):
        pac["cores"] = _CORES_COMPARACAO[i % len(_CORES_COMPARACAO)]

    # Determina modos de atividade disponíveis na interseção dos arquivos
    modos_comuns = [
        modo for modo in MODOS_ATIVIDADE
        if all(modo in pac["df"].columns for pac in pacientes_validos)
    ]
    if not modos_comuns:
        # Fallback: união — usa o primeiro disponível em cada arquivo
        modos_uniao = list({
            modo for pac in pacientes_validos
            for modo in MODOS_ATIVIDADE if modo in pac["df"].columns
        })
        if not modos_uniao:
            st.error("Nenhum modo de atividade reconhecido (PIM, TAT, ZCM) nos arquivos selecionados.")
            return
        st.warning(
            f"Nem todos os arquivos possuem os mesmos modos de atividade. "
            f"Apenas os arquivos com o modo selecionado serão plotados."
        )
        modos_disponiveis_comp = modos_uniao
    else:
        modos_disponiveis_comp = modos_comuns

    col_modo, col_sinais = st.columns([2, 3])
    with col_modo:
        modo_atividade_comp = st.radio(
            "Modo de atividade",
            modos_disponiveis_comp, horizontal=True,
            key="comp_modo_atividade",
        )
    with col_sinais:
        st.caption("Sinais adicionais")
        mostrar_atividade_comp = st.checkbox(
            "Atividade", key="comp_mostrar_atividade", value=True,
            help="Exibe as curvas de atividade de todos os pacientes.",
        )
        mostrar_luz_comp = st.checkbox(
            "Luz", key="comp_mostrar_luz", value=True,
            help="Exibe curvas de luz sobrepostas (somente arquivos com coluna LIGHT).",
        )
        mostrar_temp_comp = st.checkbox(
            "Temperatura", key="comp_mostrar_temp", value=True,
            help="Exibe curvas de temperatura sobrepostas (somente arquivos com coluna TEMPERATURE).",
        )

    # Determina o intervalo máximo de dias relativos (mínimo entre todos os pacientes)
    max_dias = min(
        len(pac["df"]["DATE/TIME"].dt.date.unique())
        for pac in pacientes_validos
    )
    if max_dias < 1:
        st.error("Nenhum paciente possui dados suficientes para comparação.")
        return

    col_ini, col_fim = st.columns(2)
    dia_ini_comp = col_ini.number_input(
        "Dia relativo inicial", min_value=1, max_value=max_dias, value=1,
        step=1, key="comp_dia_ini",
        help="Dia 1 = primeiro dia do registro de cada paciente.",
    )
    dia_fim_comp = col_fim.number_input(
        "Dia relativo final", min_value=1, max_value=max_dias, value=min(7, max_dias),
        step=1, key="comp_dia_fim",
    )

    if dia_ini_comp > dia_fim_comp:
        st.warning("O dia inicial deve ser menor ou igual ao dia final.")
        return

    st.divider()

    # Gera um gráfico por dia relativo no intervalo selecionado
    for dia_rel in range(int(dia_ini_comp), int(dia_fim_comp) + 1):
        # Filtra apenas pacientes que possuem dados neste dia relativo
        pacientes_dia = [
            pac for pac in pacientes_validos
            if _alinhar_dia_relativo(pac["df"], dia_rel) is not None
            and modo_atividade_comp in pac["df"].columns
        ]
        if not pacientes_dia:
            st.caption(f"Dia relativo {dia_rel} — sem dados em nenhum arquivo.")
            continue

        fig = _grafico_comparacao_dia(
            dia_relativo=dia_rel,
            pacientes=pacientes_dia,
            modo_atividade=modo_atividade_comp,
            mostrar_atividade=mostrar_atividade_comp,
            mostrar_luz=mostrar_luz_comp,
            mostrar_temperatura=mostrar_temp_comp,
        )
        st.plotly_chart(fig, width="stretch", key=f"comp_plot_{dia_rel}")

        # Tabela de resumo abaixo de cada gráfico
        with st.expander(f"Resumo estatístico — Dia relativo {dia_rel}"):
            _tabela_resumo_comparacao(
                pacientes_dia, modo_atividade_comp,
                dia_ini=dia_rel, dia_fim=dia_rel,
            )

    # Resumo geral do intervalo completo
    st.divider()
    st.subheader(f"Resumo estatístico — Dias {int(dia_ini_comp)} a {int(dia_fim_comp)}")
    _tabela_resumo_comparacao(
        pacientes_validos, modo_atividade_comp,
        dia_ini=int(dia_ini_comp), dia_fim=int(dia_fim_comp),
    )


# ── Página principal ──────────────────────────────────────────────────────────

def analises_page():
    st.title("Análises")
    st.divider()

    usuario_id = get_usuario_id()
    if not usuario_id:
        return

    render_toast()

    arquivos = ArquivoController.listar(usuario_id)
    if not arquivos:
        st.info("Nenhum arquivo enviado ainda. Acesse **Conjunto de dados** para fazer upload.")
        return

    # ── Divisão em abas ───────────────────────────────────────────────────────
    aba_individual,aba_filtro_luz, aba_comparacao  = st.tabs([
        "📊  Análise Individual",
        "💡  Filtro de Luz Global",
        "👥  Comparação entre Pacientes",
    ])

    with aba_comparacao:
        _aba_comparacao(usuario_id, arquivos)

    # ── Aba individual (lógica original, inalterada) ──────────────────────────
    with aba_individual:
        _aba_individual(usuario_id, arquivos)

    with aba_filtro_luz:
        _aba_filtro_luz(usuario_id, arquivos)


def _aba_individual(usuario_id: int, arquivos: list) -> None:
    """
    Aba de análise individual — lógica original sem nenhuma alteração.
    Não contém nenhuma referência ao filtro global de luz; esse filtro
    vive exclusivamente em _aba_filtro_luz().
    """
    opcoes_arquivo = {arq["nome"]: arq for arq in arquivos}
    nome_escolhido = st.selectbox("Arquivo", list(opcoes_arquivo.keys()), key="ind_arquivo")
    arquivo_id = opcoes_arquivo[nome_escolhido]["id"]

    metadata, df = _carregar_actigrafia(arquivo_id, usuario_id)
    if df.empty:
        st.warning("Não foi possível processar este arquivo.")
        return

    nome_sujeito = metadata.get("SUBJECT_NAME")
    col_nome, col_sexo, col_nascimento = st.columns(3)
    col_nome.caption(f"**Paciente:** {nome_sujeito.strip().upper() if nome_sujeito else '—'}")
    col_sexo.caption(f"**Sexo:** {_rotulo_genero(metadata.get('SUBJECT_GENDER'))}")
    col_nascimento.caption(f"**Data de nascimento:** {metadata.get('SUBJECT_DATE_OF_BIRTH', '—')}")

    # ── Recorte do registro ───────────────────────────────────────────────────
    descartar_inicio = st.checkbox(
        "Descartar as primeiras horas do registro",
        key="ind_descartar",
        help=(
            "Remove o início do registro — por exemplo, o período de adaptação ao "
            "dispositivo, antes que o paciente retome a rotina normal. Afeta as "
            "métricas e os gráficos a seguir, mas não altera o arquivo salvo."
        ),
    )
    if descartar_inicio:
        inicio_dt = cast(_dt.datetime, pd.Timestamp(df["DATE/TIME"].iloc[0]))
        fim_dt    = cast(_dt.datetime, pd.Timestamp(df["DATE/TIME"].iloc[-1]))

        modo_descarte = st.segmented_control(
            "Modo de corte",
            ["Por duração", "Por data e hora"],
            default="Por duração",
            label_visibility="collapsed",
            key="ind_modo_descarte",
        )
        limite_dt:     _dt.datetime | None = None
        limite_fim_dt: _dt.datetime | None = None

        if modo_descarte == "Por duração":
            col_dur_ini, col_dur_fim = st.columns(2)
            duracao_ini_h = col_dur_ini.pills(
                "Duração a descartar do início do registro",
                _DURACOES_DESCARTE_H, default=2, required=True, format_func=lambda h: f"{h}h",
                help="Remove os dados anteriores a esse intervalo, contado a partir do primeiro registro.",
            )
            if duracao_ini_h is not None:
                limite_dt = inicio_dt + _dt.timedelta(hours=int(duracao_ini_h))

            duracao_fim_h = col_dur_fim.pills(
                "Duração a descartar do fim do registro",
                _DURACOES_DESCARTE_H, default=None, format_func=lambda h: f"{h}h",
                help="Remove os dados posteriores a esse intervalo, contado a partir do último registro.",
            )
            if duracao_fim_h is not None:
                limite_fim_dt = fim_dt - _dt.timedelta(hours=int(duracao_fim_h))

        else:
            col_label_ini, _, col_label_fim = st.columns([2, 0.5, 2])
            col_label_ini.markdown("**Início**")
            col_label_fim.markdown("**Fim**")
            col_data_ini, col_hora_ini, _sep, col_data_fim, col_hora_fim = st.columns([2, 2, 0.5, 2, 2])

            data_ini = col_data_ini.date_input(
                "Data de início da análise",
                value=inicio_dt.date(), min_value=inicio_dt.date(), max_value=fim_dt.date(),
                format="DD/MM/YYYY",
            )
            hora_ini_corte = col_hora_ini.time_input(
                "Hora de início da análise", value=inicio_dt.time(), step=300,
            )
            if isinstance(data_ini, _dt.date) and hora_ini_corte:
                limite_dt = _dt.datetime.combine(data_ini, hora_ini_corte)

            data_fim = col_data_fim.date_input(
                "Data de fim da análise",
                value=fim_dt.date(), min_value=inicio_dt.date(), max_value=fim_dt.date(),
                format="DD/MM/YYYY",
            )
            hora_fim_corte = col_hora_fim.time_input(
                "Hora de fim da análise", value=fim_dt.time(), step=300,
            )
            if isinstance(data_fim, _dt.date) and hora_fim_corte:
                limite_fim_dt = _dt.datetime.combine(data_fim, hora_fim_corte)

        if limite_dt is not None and limite_dt > inicio_dt:
            df = df[df["DATE/TIME"] >= limite_dt].copy()
        if limite_fim_dt is not None and limite_fim_dt < fim_dt:
            df = df[df["DATE/TIME"] <= limite_fim_dt].copy()
        if df.empty:
            st.warning("O intervalo selecionado não contém dados — ajuste os valores.")
            return

    tem_evento = "EVENT" in df.columns

    modos_disponiveis = [modo for modo in MODOS_ATIVIDADE if modo in df.columns]
    if not modos_disponiveis:
        st.warning("Este arquivo não possui nenhuma coluna de atividade reconhecida (PIM, TAT ou ZCM).")
        return

    luz_bruta  = _coluna_numerica_utilizavel(df, "LIGHT")
    temp_bruta = _coluna_numerica_utilizavel(df, "TEMPERATURE")
    tem_luz         = luz_bruta  is not None
    tem_temperatura = temp_bruta is not None

    faixa_total_luz  = (0.0, float(luz_bruta.max()))                      if luz_bruta  is not None else None
    faixa_total_temp = (float(temp_bruta.min()), float(temp_bruta.max())) if temp_bruta is not None else None

    # ── Opções de exibição ────────────────────────────────────────────────────
    with st.expander("Opções de exibição"):
        modo_atividade = st.radio(
            "Modo de atividade", modos_disponiveis, horizontal=True,
            help="Medida de atividade motora usada no gráfico e no cálculo do ritmo de repouso-atividade.",
        )
        faixa_total_atividade = (0.0, float(df[modo_atividade].max()))

        mascarar_inatividade = st.checkbox(
            "Mascarar períodos de inatividade prolongada",
            help=(
                "Usa o pyActigraphy para identificar sequências de valor zero mais longas "
                "que a duração escolhida — provavelmente o sensor foi removido — e tratá-las "
                "como dados ausentes, tanto no gráfico quanto nas métricas de ritmo."
            ),
        )
        duracao_mascara_h = None
        if mascarar_inatividade:
            duracao_mascara_h = st.pills(
                "Duração mínima considerada inatividade",
                _DURACOES_MASCARA_H, default=2, required=True, format_func=lambda h: f"{h}h",
                help=(
                    "Sequências de zeros mais curtas que esse intervalo são preservadas — "
                    "provavelmente são períodos normais de repouso, não remoção do sensor. "
                    "O pyActigraphy recomenda ao menos 2h para não mascarar o sono."
                ),
            )

        st.divider()
        st.caption("Sinais exibidos no gráfico")
        col_a, col_l, col_t = st.columns(3, gap="medium")

        mostrar_atividade = col_a.checkbox(f"Atividade ({modo_atividade})", value=True)
        escala_atividade = faixa_total_atividade
        if mostrar_atividade and faixa_total_atividade[0] < faixa_total_atividade[1]:
            escala_atividade = col_a.slider(
                f"Faixa exibida ({modo_atividade})",
                min_value=faixa_total_atividade[0], max_value=faixa_total_atividade[1],
                value=faixa_total_atividade,
                help="Recorta o eixo da atividade para a faixa de valores selecionada, sem alterar os dados originais.",
            )

        mostrar_luz = col_l.checkbox(
            "Luz", value=tem_luz, disabled=not tem_luz,
            help=None if tem_luz else "Este arquivo não possui registros de luz utilizáveis (coluna LIGHT).",
        )
        escala_luz = faixa_total_luz
        if mostrar_luz and faixa_total_luz is not None and faixa_total_luz[0] < faixa_total_luz[1]:
            escala_luz = col_l.slider(
                "Faixa exibida (Lux)",
                min_value=faixa_total_luz[0], max_value=faixa_total_luz[1], value=faixa_total_luz,
                help="Recorta o eixo da luz para a faixa de valores selecionada, sem alterar os dados originais.",
            )

        mostrar_temperatura = col_t.checkbox(
            "Temperatura", value=tem_temperatura, disabled=not tem_temperatura,
            help=None if tem_temperatura else "Este arquivo não possui registros de temperatura utilizáveis (coluna TEMPERATURE).",
        )
        escala_temperatura = faixa_total_temp
        if mostrar_temperatura and faixa_total_temp is not None and faixa_total_temp[0] < faixa_total_temp[1]:
            escala_temperatura = col_t.slider(
                "Faixa exibida (°C)",
                min_value=faixa_total_temp[0], max_value=faixa_total_temp[1], value=faixa_total_temp,
                help="Recorta o eixo da temperatura para a faixa de valores selecionada, sem alterar os dados originais.",
            )

        st.divider()
        mostrar_eventos = st.checkbox(
            "Destacar marcações de evento (botão)",
            disabled=not tem_evento,
            help=None if tem_evento else "Este arquivo não possui registros de marcação de evento (coluna EVENT).",
        )

    # mask_h consolidado uma única vez; alimenta tanto o raw dos gráficos
    # quanto as funções cacheadas de cálculo de métricas
    mask_h = int(duracao_mascara_h) if mascarar_inatividade and duracao_mascara_h is not None else None

    # raw usado apenas para raw.data.loc[dia] nos gráficos;
    # @st.cache_data entrega uma cópia deserializada → mutação da máscara é segura
    raw = _construir_raw_cached(nome_escolhido, df, modo_atividade)
    if mask_h is not None:
        raw.create_inactivity_mask(f"{mask_h}h")
        raw.mask_inactivity = True

    dias = ArquivoController.dias_disponiveis(df)
    # numeração "Dia N" preservada antes da filtragem de exibição
    numero_por_dia = {dia: numero for numero, dia in enumerate(dias, start=1)}

    # ── Filtros de exibição ───────────────────────────────────────────────────
    with st.expander("Filtrar dias exibidos"):
        st.caption("Filtros apenas de exibição — recortam os gráficos abaixo sem alterar os dados nem as métricas do registro completo.")

        col_semana, col_periodo = st.columns(2, gap="large")

        with col_semana:
            st.caption("Dia da semana")
            dias_semana_escolhidos = st.pills(
                "Dia da semana", _DIAS_SEMANA, selection_mode="multi", default=_DIAS_SEMANA,
                label_visibility="collapsed",
                help="Mostra apenas os gráficos dos dias que caem nos dias da semana selecionados.",
            ) or []

        with col_periodo:
            st.caption("Período do dia")
            rotulo_periodo = st.segmented_control(
                "Período do dia", [*_PERIODOS_DIA.keys(), "Personalizado"],
                default="Dia inteiro", required=True, label_visibility="collapsed",
                help="Recorta a janela de horário exibida em cada gráfico diário.",
            )
            if rotulo_periodo == "Personalizado":
                hora_inicio, hora_fim = st.slider(
                    "Intervalo de horário personalizado", min_value=0, max_value=24, value=(0, 24),
                    step=1, format="%dh", label_visibility="collapsed",
                )
            else:
                hora_inicio, hora_fim = _PERIODOS_DIA[rotulo_periodo]

    dias_exibidos = [
        dia for dia in dias
        if _DIAS_SEMANA[pd.Timestamp(dia).weekday()] in dias_semana_escolhidos
    ]

    # DatetimeIndex pré-computado uma única vez e reutilizado nas três séries
    dt_index = pd.DatetimeIndex(df["DATE/TIME"])

    serie_evento = None
    if mostrar_eventos and tem_evento:
        serie_evento = pd.Series(
            pd.to_numeric(df["EVENT"], errors="coerce").to_numpy(),
            index=dt_index, name="evento",
        )

    serie_luz = None
    if mostrar_luz and luz_bruta is not None:
        serie_luz = pd.Series(luz_bruta.to_numpy(), index=dt_index, name="luz")

    serie_temp = None
    if mostrar_temperatura and temp_bruta is not None:
        serie_temp = pd.Series(temp_bruta.to_numpy(), index=dt_index, name="temperatura")

    if not (mostrar_atividade or serie_luz is not None or serie_temp is not None):
        st.info("Selecione ao menos um sinal em **Opções de exibição** para gerar o gráfico.")
        return

    # ── Configurações de métricas não paramétricas ────────────────────────────
    with st.expander("Configurações das medidas não paramétricas"):
        st.caption("Ajustam o cálculo de IS, IV, L5 e M10 abaixo — não alteram os dados nem os gráficos.")
        col_freq, col_limiar = st.columns(2, gap="medium")
        frequencia_metricas = col_freq.selectbox(
            "Frequência de reamostragem (IS e IV)",
            ["10min", "15min", "30min", "1H", "2H"], index=3,
            help=(
                "Janela de tempo usada para agregar os dados antes de calcular IS e IV — "
                "janelas menores aumentam a sensibilidade à fragmentação intradiária."
            ),
        )
        limiar_atividade = col_limiar.number_input(
            "Limiar de binarização (IS, IV, L5 e M10)",
            min_value=0, value=4, step=1,
            help="Valores de atividade a partir deste limiar contam como 'ativo' (1); abaixo dele, como 'inativo' (0).",
        )

        st.divider()
        usar_periodo = st.checkbox(
            "Calcular por período",
            help="Usa ISp, IVp, L5p e M10p — calcula as medidas separadamente para cada janela de tempo do registro.",
        )
        periodo_metricas = "7D"
        if usar_periodo:
            dias_registro  = len(dias)
            opcoes_periodo = [(label, val) for d, label, val in _PERIODOS_FIXOS if d <= dias_registro // 2]
            if not opcoes_periodo:
                opcoes_periodo = [("1 dia", "1D")]
            labels_periodo   = [l for l, _ in opcoes_periodo]
            vals_map_periodo = {l: v for l, v in opcoes_periodo}
            escolha_periodo  = st.selectbox(
                "Período de análise", labels_periodo,
                help=f"Registro com {dias_registro} dia(s). Apenas períodos que permitem ao menos 2 janelas são exibidos.",
            )
            periodo_metricas = vals_map_periodo[escolha_periodo] if escolha_periodo else "1D"

    _metricas_ritmo(
        df=df, nome=nome_escolhido, coluna=modo_atividade,
        titulo="Ritmo de repouso-atividade — registro completo",
        freq=frequencia_metricas, limiar=int(limiar_atividade),
        usar_periodo=usar_periodo, periodo=periodo_metricas,
        mask_h=mask_h,
    )
    st.divider()

    if not dias_exibidos:
        st.info("Nenhum dia do registro corresponde aos filtros selecionados em **Filtrar dias exibidos**.")
    else:
        for dia in dias_exibidos:
            st.plotly_chart(
                _grafico_combinado_dia(
                    dia, numero_por_dia[dia], raw.data.loc[dia],
                    escala_atividade, modo_atividade, cor_atividade=COR_LINHA,
                    mostrar_atividade=mostrar_atividade,
                    serie_luz=serie_luz, serie_temp=serie_temp, serie_evento=serie_evento,
                    escala_luz=escala_luz, escala_temperatura=escala_temperatura,
                    hora_inicio=hora_inicio, hora_fim=hora_fim,
                ),
                width="stretch",
                key=f"ind_plot_{dia}",
            )

    # ── Exportação dos dados ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Exportar dados")
    st.caption(
        "Gera um .zip com os dados do registro após os recortes aplicados acima: "
        "um .txt no formato original (mesmas linhas de cabeçalho e campos) e um "
        ".csv apenas com os campos e seus valores. Sinais não selecionados em "
        "**Opções de exibição**, valores fora das faixas exibidas e linhas fora "
        "de **Filtrar dias exibidos** são exportados zerados; períodos mascarados "
        "como inatividade são exportados vazios (dado ausente)."
    )
    df_exportar = _preparar_df_exportacao(
        df, dt_index, modos_disponiveis, modo_atividade,
        mostrar_atividade, escala_atividade, raw, mask_h,
        mostrar_luz, escala_luz, mostrar_temperatura, escala_temperatura,
        dias_exibidos, hora_inicio, hora_fim,
    )
    zip_bytes, zip_nome = _gerar_export_zip(arquivo_id, usuario_id, df_exportar)
    if zip_bytes:
        st.download_button(
            "Baixar dados (.zip)", data=zip_bytes, file_name=zip_nome, mime="application/zip",
            on_click=_salvar_relatorio, args=(usuario_id, nome_escolhido, zip_nome, zip_bytes),
        )
        st.caption("Uma cópia também é salva em **Exportar relatório**.")
    else:
        st.warning("Não foi possível gerar a exportação.")


# ══════════════════════════════════════════════════════════════════════════════
# ABA DE ANÁLISE POR FAIXA DE LUZ
# ══════════════════════════════════════════════════════════════════════════════

def _aba_filtro_luz(usuario_id: int, arquivos: list) -> None:
    """
    Aba isolada para análise por faixa de iluminação.

    Reutiliza o mesmo arquivo selecionado na aba individual e aplica
    _aplicar_filtro_global_luz() ao DataFrame completo antes de qualquer
    cálculo. Toda a lógica de gráficos, métricas e exportação é idêntica
    à aba individual — a única diferença é que o df já chega filtrado.

    Não interfere em nenhuma variável de state da aba individual.
    """
    opcoes_arquivo = {arq["nome"]: arq for arq in arquivos}
    nome_escolhido = st.selectbox("Arquivo", list(opcoes_arquivo.keys()), key="ind_arquivo_luz")
    arquivo_id = opcoes_arquivo[nome_escolhido]["id"]

    arquivo_id = next(
        (arq["id"] for arq in arquivos if arq["nome"] == nome_escolhido), None
    )
    if arquivo_id is None:
        st.warning("Arquivo não encontrado.")
        return

    metadata, df_original = _carregar_actigrafia(arquivo_id, usuario_id)
    if df_original.empty:
        st.warning("Não foi possível processar este arquivo.")
        return

    nome_sujeito = metadata.get("SUBJECT_NAME")
    col_nome, col_sexo, col_nasc = st.columns(3)
    col_nome.caption(f"**Paciente:** {nome_sujeito.strip().upper() if nome_sujeito else '—'}")
    col_sexo.caption(f"**Sexo:** {_rotulo_genero(metadata.get('SUBJECT_GENDER'))}")
    col_nasc.caption(f"**Data de nascimento:** {metadata.get('SUBJECT_DATE_OF_BIRTH', '—')}")

    # ── Verificação de coluna LIGHT ───────────────────────────────────────────
    luz_original = _coluna_numerica_utilizavel(df_original, "LIGHT")
    if luz_original is None:
        st.warning(
            "Este arquivo não possui registros de luz utilizáveis (coluna LIGHT). "
            "A análise por faixa de luz não está disponível para este arquivo."
        )
        return

    faixa_total_luz = (0.0, float(luz_original.max()))

    # ── Filtro Global Baseado em Luz ──────────────────────────────────────────
    st.subheader("Filtro Global Baseado em Luz")
    st.caption(
        "Considera apenas os momentos em que a luz (Lux) esteve dentro da faixa "
        "selecionada."
    )

    faixa_filtro_luz: tuple[float, float] = faixa_total_luz
    if faixa_total_luz[0] < faixa_total_luz[1]:
        faixa_filtro_luz = st.slider(
            "Faixa de luz (Lux)",
            min_value=faixa_total_luz[0],
            max_value=faixa_total_luz[1],
            value=faixa_total_luz,
            key="fl_slider_luz",
            help=(
                "Apenas os registros com LIGHT dentro desta faixa serão mantidos. "
                "Os eixos dos gráficos, métricas e exportação são recalculados "
                "automaticamente com base nos dados restantes."
            ),
        )
    else:
        st.info(f"A coluna LIGHT possui valor único ({faixa_total_luz[0]:.0f} Lux) — nenhuma filtragem disponível.")
        return

    # ── Aplicar filtro ao DataFrame completo ──────────────────────────────────
    # A partir daqui, df é o DataFrame filtrado. Nenhuma série, faixa ou
    # variável calculada antes deste ponto é reutilizada nos cálculos abaixo.
    df = _aplicar_filtro_global_luz(df_original, faixa_filtro_luz)

    n_original = len(df_original)
    n_filtrado = len(df)
    st.caption(
        f"Registros mantidos: **{n_filtrado:,}** de {n_original:,} "
        f"({100 * n_filtrado / n_original:.1f}%) — "
        f"faixa: {faixa_filtro_luz[0]:.0f}–{faixa_filtro_luz[1]:.0f} Lux."
    )

    if df.empty:
        st.warning(
            "O filtro removeu todos os registros. "
            "Amplie a faixa de luz para incluir mais dados."
        )
        return

    # ── Reconstrução de todas as séries e faixas com base no df filtrado ──────
    modos_disponiveis = [modo for modo in MODOS_ATIVIDADE if modo in df.columns]
    if not modos_disponiveis:
        st.warning("O df filtrado não possui nenhuma coluna de atividade reconhecida (PIM, TAT ou ZCM).")
        return

    tem_evento      = "EVENT" in df.columns
    luz_filtrada    = _coluna_numerica_utilizavel(df, "LIGHT")
    temp_filtrada   = _coluna_numerica_utilizavel(df, "TEMPERATURE")
    tem_temperatura = temp_filtrada is not None

    # Faixas recalculadas exclusivamente com os dados que sobraram
    modo_atividade = modos_disponiveis[0]
    faixa_ativ = (
        float(df[modo_atividade].min()),
        float(df[modo_atividade].max()),
    )
    faixa_luz = (
        float(luz_filtrada.min()),
        float(luz_filtrada.max()),
    ) if luz_filtrada is not None else None
    faixa_temp = (
        float(temp_filtrada.min()),
        float(temp_filtrada.max()),
    ) if temp_filtrada is not None else None

    mostrar_atividade = True
    mostrar_luz = True
    mostrar_temperatura = tem_temperatura

    # ── Opções de exibição ────────────────────────────────────────────────────
    with st.expander("Opções de exibição"):
        modo_atividade = st.radio(
            "Modo de atividade", modos_disponiveis, horizontal=True,
            key="fl_modo_atividade",
            help="Medida de atividade motora usada no gráfico e no cálculo do ritmo de repouso-atividade.",
        )
        faixa_ativ = (
            float(df[modo_atividade].min()),
            float(df[modo_atividade].max()),
        )

        mascarar_inatividade = st.checkbox(
            "Mascarar períodos de inatividade prolongada",
            key="fl_mascarar",
            help=(
                "Usa o pyActigraphy para identificar sequências de valor zero mais longas "
                "que a duração escolhida e tratá-las como dados ausentes."
            ),
        )
        duracao_mascara_h = None
        if mascarar_inatividade:
            duracao_mascara_h = st.pills(
                "Duração mínima considerada inatividade",
                _DURACOES_MASCARA_H, default=2, required=True, format_func=lambda h: f"{h}h",
                key="fl_duracao_mascara",
                help="Sequências de zeros mais curtas que esse intervalo são preservadas.",
            )

        st.divider()
        mostrar_eventos = st.checkbox(
            "Destacar marcações de evento (botão)",
            key="fl_show_eventos", disabled=not tem_evento,
            help=None if tem_evento else "Este arquivo não possui registros de marcação de evento.",
        )

    # ── Construção das séries temporais (todas a partir do df filtrado) ────────
    mask_h = int(duracao_mascara_h) if mascarar_inatividade and duracao_mascara_h is not None else None

    raw = _construir_raw_cached(nome_escolhido, df, modo_atividade)
    if mask_h is not None:
        raw.create_inactivity_mask(f"{mask_h}h")
        raw.mask_inactivity = True

    dias = ArquivoController.dias_disponiveis(df)
    numero_por_dia = {dia: numero for numero, dia in enumerate(dias, start=1)}

    # ── Filtros de exibição ───────────────────────────────────────────────────
    with st.expander("Filtrar dias exibidos"):
        st.caption("Filtros apenas de exibição — não alteram os dados filtrados nem as métricas.")

        col_semana, col_periodo = st.columns(2, gap="large")
        with col_semana:
            st.caption("Dia da semana")
            dias_semana_escolhidos = st.pills(
                "Dia da semana", _DIAS_SEMANA, selection_mode="multi",
                default=_DIAS_SEMANA, label_visibility="collapsed",
                key="fl_dias_semana",
            ) or []
        with col_periodo:
            st.caption("Período do dia")
            rotulo_periodo = st.segmented_control(
                "Período do dia", [*_PERIODOS_DIA.keys(), "Personalizado"],
                default="Dia inteiro", required=True, label_visibility="collapsed",
                key="fl_periodo_dia",
            )
            if rotulo_periodo == "Personalizado":
                hora_inicio, hora_fim = st.slider(
                    "Intervalo de horário personalizado", min_value=0, max_value=24,
                    value=(0, 24), step=1, format="%dh", label_visibility="collapsed",
                    key="fl_hora_personalizada",
                )
            else:
                hora_inicio, hora_fim = _PERIODOS_DIA[rotulo_periodo]

    dias_exibidos = [
        dia for dia in dias
        if _DIAS_SEMANA[pd.Timestamp(dia).weekday()] in dias_semana_escolhidos
    ]

    dt_index = pd.DatetimeIndex(df["DATE/TIME"])

    serie_evento = None
    if tem_evento:
        serie_evento = pd.Series(
            pd.to_numeric(df["EVENT"], errors="coerce").to_numpy(),
            index=dt_index, name="evento",
        )

    serie_luz = pd.Series(luz_filtrada.to_numpy(), index=dt_index, name="luz") if luz_filtrada is not None else None
    serie_temp = pd.Series(temp_filtrada.to_numpy(), index=dt_index, name="temperatura") if temp_filtrada is not None else None

    escala_atividade = faixa_ativ
    escala_luz = faixa_luz
    escala_temperatura = faixa_temp

    # ── Configurações de métricas não paramétricas ────────────────────────────
    with st.expander("Configurações das medidas não paramétricas"):
        st.caption("Ajustam o cálculo de IS, IV, L5 e M10 — calculados sobre os dados filtrados por luz.")
        col_freq, col_limiar = st.columns(2, gap="medium")
        frequencia_metricas = col_freq.selectbox(
            "Frequência de reamostragem (IS e IV)",
            ["10min", "15min", "30min", "1H", "2H"], index=3,
            key="fl_freq_metricas",
            help="Janela de tempo usada para agregar os dados antes de calcular IS e IV.",
        )
        limiar_atividade = col_limiar.number_input(
            "Limiar de binarização (IS, IV, L5 e M10)",
            min_value=0, value=4, step=1, key="fl_limiar_atividade",
            help="Valores a partir deste limiar contam como 'ativo' (1); abaixo dele, como 'inativo' (0).",
        )
        st.divider()
        usar_periodo = st.checkbox(
            "Calcular por período", key="fl_usar_periodo",
            help="Usa ISp, IVp, L5p e M10p — calcula as medidas para cada janela de tempo.",
        )
        periodo_metricas = "7D"
        if usar_periodo:
            dias_registro  = len(dias)
            opcoes_periodo = [(label, val) for d, label, val in _PERIODOS_FIXOS if d <= dias_registro // 2]
            if not opcoes_periodo:
                opcoes_periodo = [("1 dia", "1D")]
            labels_periodo   = [l for l, _ in opcoes_periodo]
            vals_map_periodo = {l: v for l, v in opcoes_periodo}
            escolha_periodo  = st.selectbox(
                "Período de análise", labels_periodo, key="fl_periodo_escolhido",
                help=f"Registro com {dias_registro} dia(s). Apenas períodos que permitem ao menos 2 janelas são exibidos.",
            )
            periodo_metricas = vals_map_periodo[escolha_periodo] if escolha_periodo else "1D"

    # Métricas calculadas sobre o df filtrado
    _metricas_ritmo(
        df=df, nome=nome_escolhido, coluna=modo_atividade,
        titulo="Ritmo de repouso-atividade — dados filtrados por luz",
        freq=frequencia_metricas, limiar=int(limiar_atividade),
        usar_periodo=usar_periodo, periodo=periodo_metricas,
        mask_h=mask_h,
    )
    st.divider()

    # ── Gráficos diários ──────────────────────────────────────────────────────
    if not dias_exibidos:
        st.info("Nenhum dia do registro corresponde aos filtros selecionados em **Filtrar dias exibidos**.")
    else:
        for dia in dias_exibidos:
            st.plotly_chart(
                _grafico_combinado_dia(
                    dia, numero_por_dia[dia], raw.data.loc[dia],
                    escala_atividade, modo_atividade, cor_atividade=COR_LINHA,
                    mostrar_atividade=True,
                    serie_luz=serie_luz, serie_temp=serie_temp, serie_evento=serie_evento,
                    escala_luz=escala_luz, escala_temperatura=escala_temperatura,
                    hora_inicio=hora_inicio, hora_fim=hora_fim,
                ),
                width="stretch",
                key=f"fl_plot_{dia}",
            )

    # ── Exportação dos dados filtrados ────────────────────────────────────────
    st.divider()
    st.subheader("Exportar dados filtrados")
    st.caption(
        "Gera um .zip com os dados após o filtro de luz e os recortes de exibição. "
        "Os registros fora da faixa de Lux já foram removidos do DataFrame — "
        "não constam na exportação."
    )
    df_exportar = _preparar_df_exportacao(
        df, dt_index, modos_disponiveis, modo_atividade,
        True, faixa_ativ, raw, mask_h,
        True, faixa_luz, mostrar_temperatura, faixa_temp,
        dias_exibidos, hora_inicio, hora_fim,
    )
    zip_bytes, zip_nome = _gerar_export_zip(arquivo_id, usuario_id, df_exportar)
    if zip_bytes:
        nome_zip_filtrado = zip_nome.replace("_exportado", "_filtrado_luz")
        st.download_button(
            "Baixar dados filtrados (.zip)", data=zip_bytes,
            file_name=nome_zip_filtrado, mime="application/zip",
            on_click=_salvar_relatorio,
            args=(usuario_id, nome_escolhido, nome_zip_filtrado, zip_bytes),
        )
        st.caption("Uma cópia também é salva em **Exportar relatório**.")
    else:
        st.warning("Não foi possível gerar a exportação.")
