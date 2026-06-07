
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from pyActigraphy.io import BaseRaw
import streamlit as st
from controller.arquivo_controller import ArquivoController
from view.ui import render_toast, get_usuario_id


COR_LINHA = "#234cbe"
COR_LEGENDA = "black"
COR_SOMBRA_NOITE = "rgba(25, 35, 90, 0.12)"
COR_SOMBRA_EVENTO = "rgba(34, 139, 34, 0.18)"

MODOS_ATIVIDADE = ["PIM", "TAT", "ZCM"]

@st.cache_data(ttl=120)
def _carregar_actigrafia(arquivo_id: int, usuario_id: int) -> tuple:
    return ArquivoController.carregar_actigrafia(arquivo_id, usuario_id)


def _construir_raw(nome: str, df: pd.DataFrame, coluna: str) -> BaseRaw:
    serie = pd.Series(df[coluna].to_numpy(), index=pd.DatetimeIndex(df["DATE/TIME"]), name="Activity")
    frequencia = pd.Timedelta(serie.index.to_series().diff().median())
    serie = serie.asfreq(frequencia)

    return BaseRaw(
        name=nome,
        uuid=nome,
        format="CONDOR",
        axial_mode=None,
        start_time=serie.index[0],
        period=serie.index[-1] - serie.index[0],
        frequency=frequencia,
        data=serie,
        light=None,
    )


def _sombrear_periodo_noturno(fig: go.Figure, inicio: pd.Timestamp, row: int | str = "all", col: int | str = "all") -> None:
    # noite cruza a meia-noite: sombreia 00h-06h (madrugada) e 18h-24h (entrada da noite)
    for ini, fim in (
        (inicio, inicio + pd.Timedelta(hours=6)),
        (inicio + pd.Timedelta(hours=18), inicio + pd.Timedelta(days=1)),
    ):
        fig.add_vrect(x0=ini, x1=fim, fillcolor=COR_SOMBRA_NOITE, line_width=0, layer="below", row=row, col=col)


def _intervalos_marcados(mascara: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    intervalos = []
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


def _sombrear_eventos(fig: go.Figure, serie_evento: pd.Series, dia: str, row: int | str = "all", col: int | str = "all") -> None:
    try:
        fatia = serie_evento.loc[dia]
    except KeyError:
        return
    # EVENT registra a marcação do botão como contagem (não necessariamente 1);
    # qualquer valor diferente de zero indica que houve marcação no intervalo.
    marcado = fatia.fillna(0) != 0
    for ini, fim in _intervalos_marcados(marcado):
        fig.add_vrect(x0=ini, x1=fim, fillcolor=COR_SOMBRA_EVENTO, line_width=0, layer="below", row=row, col=col)


def _rotulo_dia(numero_dia: int, dia: str) -> str:
    return f"Dia {numero_dia} — {pd.Timestamp(dia).strftime('%d/%m/%Y')}"


def _grafico_dia(serie: pd.Series, dia: str, numero_dia: int, escala_y: tuple[float, float], modo_atividade: str, serie_evento: pd.Series | None = None) -> go.Figure:
    inicio = pd.Timestamp(dia)
    fim = inicio + pd.Timedelta(hours=23, minutes=59, seconds=59)

    fig = go.Figure(
        data=[go.Scatter(x=serie.index, y=serie.values, mode="lines", name="Atividade", line=dict(color=COR_LINHA))],
        layout=go.Layout(
            title=_rotulo_dia(numero_dia, dia),
            xaxis=dict(title="Hora", range=[inicio, fim], tickformat="%H:%M"),
            yaxis=dict(title=f"Atividade ({modo_atividade})", range=escala_y),
            height=300,
            margin=dict(l=0, r=0, t=40, b=0),
        ),
    )
    _sombrear_periodo_noturno(fig, inicio)
    if serie_evento is not None:
        _sombrear_eventos(fig, serie_evento, dia)
    return fig


def _grafico_todos_os_dias(raw: BaseRaw, dias: list[str], escala_y: tuple[float, float], modo_atividade: str, serie_evento: pd.Series | None = None) -> go.Figure:
    n = len(dias)
    altura_por_dia = 250
    espaco_vertical = min(0.015, 1 / (n - 1)) if n > 1 else 0

    fig = make_subplots(rows=n, cols=1, vertical_spacing=espaco_vertical)

    for i, dia in enumerate(dias, start=1):
        serie = raw.data.loc[dia]
        inicio = pd.Timestamp(dia)
        fim = inicio + pd.Timedelta(hours=23, minutes=59, seconds=59)

        fig.add_trace(
            go.Scatter(x=serie.index, y=serie.values, mode="lines", name="Atividade", line=dict(color=COR_LINHA), showlegend=False),
            row=i, col=1,
        )
        fig.update_xaxes(range=[inicio, fim], tickformat="%H:%M", row=i, col=1)
        fig.update_yaxes(range=escala_y, row=i, col=1)
        _sombrear_periodo_noturno(fig, inicio, row=i, col=1)
        if serie_evento is not None:
            _sombrear_eventos(fig, serie_evento, dia, row=i, col=1)

        eixo_y = "y domain" if i == 1 else f"y{i} domain"

        # nome do modo — dentro da área do gráfico, canto superior esquerdo (não disputa espaço com a margem)
        fig.add_annotation(
            text=modo_atividade,
            xref="x domain", yref=eixo_y,
            x=0.01, y=0.95,
            xanchor="left", yanchor="top",
            showarrow=False,
            font=dict(size=11, color=COR_LEGENDA),
        )
        # rótulo do dia — na margem esquerda, na vertical, fora da área do gráfico
        fig.add_annotation(
            text=_rotulo_dia(i, dia),
            xref="paper", yref=eixo_y,
            x=0, xshift=-55,
            y=0.5,
            xanchor="center", yanchor="middle",
            showarrow=False,
            textangle=-90,
            font=dict(size=12, color=COR_LEGENDA),
        )

    fig.update_layout(height=altura_por_dia * n, margin=dict(l=90, r=0, t=10, b=0), showlegend=False)
    return fig


_ERROS_METRICA_RITMO = (KeyError, ValueError, ZeroDivisionError)
_AVISO_DADOS_INSUFICIENTES = (
    "Não foi possível calcular esta métrica para o registro selecionado — "
    "o pyActigraphy exige pelo menos 24h de dados contínuos para estimar o ritmo de repouso-atividade."
)


def _metricas_ritmo(raw: BaseRaw, titulo: str = "Ritmo de repouso-atividade", rotulo_escopo: str = "geral", mostrar_is: bool = True, mostrar_periodos: bool = True) -> None:
    st.subheader(titulo)

    # IS/IV/L5/M10 dependem de uma janela de atividade média ao longo do
    # dia; com registros curtos ou cheios de lacunas, o pyActigraphy chega
    # a uma janela vazia/toda NaN e KeyError: NaT ao buscar seu mínimo/máximo.
    try:
        valor_iv, valor_l5, valor_m10 = raw.IV(), raw.L5(), raw.M10()
        valor_is = raw.IS() if mostrar_is else None
    except _ERROS_METRICA_RITMO:
        st.info(_AVISO_DADOS_INSUFICIENTES)
    else:
        col_is, col_iv, col_l5, col_m10 = st.columns(4)
        if mostrar_is:
            col_is.metric(f"IS — {rotulo_escopo}", f"{valor_is:.3f}",
                          help="Estabilidade interdiária: o quanto o padrão de repouso-atividade se repete de um dia para o outro.")
        else:
            # IS compara o padrão de repouso-atividade ENTRE dias — em um
            # único dia, a "média diária" é o próprio dia e a métrica sempre
            # daria 1.000 (variância sobre ela mesma), um valor sem sentido.
            col_is.metric("IS", "—",
                          help="Estabilidade interdiária compara o padrão de repouso-atividade entre vários dias; "
                               "não é uma métrica definida para um único dia.")
        col_iv.metric(f"IV — {rotulo_escopo}", f"{valor_iv:.3f}",
                      help="Variabilidade intradiária: o quanto a atividade se fragmenta ao longo do dia.")
        col_l5.metric(f"L5 — {rotulo_escopo}", f"{valor_l5:.3f}",
                      help="Atividade média durante as 5 horas menos ativas do dia (média entre todos os dias do registro).")
        col_m10.metric(f"M10 — {rotulo_escopo}", f"{valor_m10:.3f}",
                       help="Atividade média durante as 10 horas mais ativas do dia (média entre todos os dias do registro).")

    if not mostrar_periodos:
        return

    with st.expander("Valores por período de 24h"):
        try:
            is_p = raw.ISp(period="1D")
            iv_p = raw.IVp(period="1D")
            l5_p = raw.L5p(period="1D")
            m10_p = raw.M10p(period="1D")
        except _ERROS_METRICA_RITMO:
            st.info(_AVISO_DADOS_INSUFICIENTES)
            return

        inicio = raw.data.index[0]

        tabela = pd.DataFrame({
            "Período": [
                f"{(inicio + i * pd.Timedelta(days=1)).strftime('%d/%m/%Y %Hh%M')} "
                f"– {(inicio + (i + 1) * pd.Timedelta(days=1)).strftime('%d/%m/%Y %Hh%M')}"
                for i in range(len(is_p))
            ],
            "IS": is_p,
            "IV": iv_p,
            "L5": l5_p,
            "M10": m10_p,
        })
        st.dataframe(
            tabela,
            hide_index=True,
            width="stretch",
            column_config={
                coluna: st.column_config.NumberColumn(format="%.3f")
                for coluna in ("IS", "IV", "L5", "M10")
            },
        )


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

    opcoes = {arq["nome"]: arq for arq in arquivos}
    nome_escolhido = st.selectbox("Arquivo", list(opcoes.keys()))
    arquivo_id = opcoes[nome_escolhido]["id"]

    _, df = _carregar_actigrafia(arquivo_id, usuario_id)
    if df.empty:
        st.warning("Não foi possível processar este arquivo.")
        return

    tem_evento = "EVENT" in df.columns

    with st.expander("Opções de exibição"):
        modo_atividade = st.radio("Modo de atividade", MODOS_ATIVIDADE, horizontal=True)
        mostrar_eventos = st.checkbox(
            "Destacar marcações de evento (botão)",
            disabled=not tem_evento,
            help=None if tem_evento else "Este arquivo não possui registros de marcação de evento (coluna EVENT).",
        )

    raw = _construir_raw(nome_escolhido, df, modo_atividade)
    dias = ArquivoController.dias_disponiveis(df)
    escala_y = (0, float(raw.data.max()))

    serie_evento = None
    if mostrar_eventos and tem_evento:
        eventos = pd.to_numeric(df["EVENT"], errors="coerce")
        serie_evento = pd.Series(eventos.to_numpy(), index=pd.DatetimeIndex(df["DATE/TIME"]), name="evento")

    modo = st.radio("Exibir", ["Um dia específico", "Todos os dias"], horizontal=True)

    if modo == "Um dia específico":
        rotulos = {_rotulo_dia(i, dia): (i, dia) for i, dia in enumerate(dias, start=1)}
        numero_dia, dia = rotulos[st.selectbox("Dia", list(rotulos.keys()))]
        st.plotly_chart(_grafico_dia(raw.data.loc[dia], dia, numero_dia, escala_y, modo_atividade, serie_evento), width="stretch")

        st.divider()
        # recalcula IS/IV/L5/M10 a partir de um BaseRaw construído só com os
        # dados do dia selecionado, em vez de reaproveitar as métricas gerais
        df_dia = ArquivoController.filtrar_dia(df, dia)
        raw_dia = _construir_raw(f"{nome_escolhido} — {dia}", df_dia, modo_atividade)
        _metricas_ritmo(
            raw_dia,
            titulo=f"Ritmo de repouso-atividade — {_rotulo_dia(numero_dia, dia)}",
            rotulo_escopo="no dia",
            mostrar_is=False,
            mostrar_periodos=False,
        )
    else:
        st.plotly_chart(_grafico_todos_os_dias(raw, dias, escala_y, modo_atividade, serie_evento), width="stretch")

        st.divider()
        _metricas_ritmo(raw, titulo="Ritmo de repouso-atividade — registro completo")
