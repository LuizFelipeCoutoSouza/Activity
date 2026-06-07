
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from pyActigraphy.io import BaseRaw
import streamlit as st
from controller.arquivo_controller import ArquivoController
from view.ui import render_toast, get_usuario_id


COR_LINHA = "#234cbe"
COR_LEGENDA = "black"

MODOS_ATIVIDADE = {"PIM": "pim", "TAT": "TAT", "ZCM": "ZCM"}


@st.cache_data(ttl=120)
def _carregar_actigrafia(arquivo_id: int, usuario_id: int) -> tuple:
    return ArquivoController.carregar_actigrafia(arquivo_id, usuario_id)


def _construir_raw(nome: str, df: pd.DataFrame, coluna: str) -> BaseRaw:
    serie = pd.Series(df[coluna].to_numpy(), index=pd.DatetimeIndex(df["timestamp"]), name="Activity")
    frequencia = pd.Timedelta(serie.index.to_series().diff().median())

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
        fig.add_vrect(x0=ini, x1=fim, fillcolor="rgba(25, 35, 90, 0.12)", line_width=0, layer="below", row=row, col=col)


def _rotulo_dia(numero_dia: int, dia: str) -> str:
    return f"Dia {numero_dia} — {pd.Timestamp(dia).strftime('%d/%m/%Y')}"


def _grafico_dia(serie: pd.Series, dia: str, numero_dia: int, escala_y: tuple[float, float], modo_atividade: str) -> go.Figure:
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
    return fig


def _grafico_todos_os_dias(raw: BaseRaw, dias: list[str], escala_y: tuple[float, float], modo_atividade: str) -> go.Figure:
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

    with st.expander("Modo de atividade"):
        modo_atividade = st.radio("Selecione o modo", list(MODOS_ATIVIDADE.keys()), horizontal=True)
    coluna_atividade = MODOS_ATIVIDADE[modo_atividade]

    raw = _construir_raw(nome_escolhido, df, coluna_atividade)
    dias = ArquivoController.dias_disponiveis(df)
    escala_y = (0, float(raw.data.max()))

    modo = st.radio("Exibir", ["Um dia específico", "Todos os dias"], horizontal=True)

    if modo == "Um dia específico":
        rotulos = {_rotulo_dia(i, dia): (i, dia) for i, dia in enumerate(dias, start=1)}
        numero_dia, dia = rotulos[st.selectbox("Dia", list(rotulos.keys()))]
        st.plotly_chart(_grafico_dia(raw.data.loc[dia], dia, numero_dia, escala_y, modo_atividade), width="stretch")
    else:
        st.plotly_chart(_grafico_todos_os_dias(raw, dias, escala_y, modo_atividade), width="stretch")
