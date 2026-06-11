
import datetime as _dt
from typing import cast

import pandas as pd
import plotly.graph_objs as go
from pyActigraphy.io import BaseRaw
import streamlit as st
from controller.arquivo_controller import ArquivoController
from view.ui import render_toast, get_usuario_id


COR_LINHA = "#234cbe"
COR_LUZ = "#ffb433"
COR_TEMPERATURA = "#c43903"
COR_LEGENDA = "black"
COR_SOMBRA_NOITE = "rgba(25, 35, 90, 0.12)"
COR_SOMBRA_EVENTO = "rgba(34, 139, 34, 0.18)"

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


# ── Página principal ──────────────────────────────────────────────────────────

def analises2_page():
    st.title("Análise 2")
    st.divider()

    usuario_id = get_usuario_id()
    if not usuario_id:
        return

    render_toast()

    arquivos = ArquivoController.listar(usuario_id)
    if not arquivos:
        st.info("Nenhum arquivo enviado ainda. Acesse **Conjunto de dados** para fazer upload.")
        return

    opcoes_arquivo = {arq["nome"]: arq for arq in arquivos}
    nome_escolhido = st.selectbox("Arquivo", list(opcoes_arquivo.keys()))
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
    # aplicado antes de qualquer cálculo — afeta métricas, faixas e dias
    descartar_inicio = st.checkbox(
        "Descartar as primeiras horas do registro",
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

    faixa_total_luz  = (0.0, float(luz_bruta.max()))                                if luz_bruta  is not None else None
    faixa_total_temp = (float(temp_bruta.min()), float(temp_bruta.max()))            if temp_bruta is not None else None

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
        st.download_button("Baixar dados (.zip)", data=zip_bytes, file_name=zip_nome, mime="application/zip")
    else:
        st.warning("Não foi possível gerar a exportação.")
