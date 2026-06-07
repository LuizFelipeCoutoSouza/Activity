
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


_LARGURA_EIXO_EXTRA = 0.08


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
) -> go.Figure:
    inicio = pd.Timestamp(dia)
    fim = inicio + pd.Timedelta(hours=23, minutes=59, seconds=59)

    # luz e temperatura entram como eixos Y extras à direita — cada um com sua
    # própria escala — em vez de subplots separados, para permitir comparar os
    # três sinais lado a lado no tempo
    extras = [
        (rotulo, cor, serie, faixa)
        for rotulo, cor, serie, faixa in (
            ("Luz (Lux)", COR_LUZ, serie_luz, (0, float(serie_luz.max())) if serie_luz is not None else None),
            ("Temperatura (°C)", COR_TEMPERATURA, serie_temp, (float(serie_temp.min()), float(serie_temp.max())) if serie_temp is not None else None),
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
        # legenda no canto superior direito, fora da área sombreada do gráfico,
        # com fundo e borda para permanecer legível sobre as curvas e sombreados
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            bgcolor="rgba(255, 255, 255, 0.75)",
            bordercolor="rgba(0, 0, 0, 0.15)",
            borderwidth=1,
            font=dict(size=11, color=COR_LEGENDA),
        ),
    )

    for i, (rotulo, cor, serie, faixa) in enumerate(extras):
        indice_eixo = i + 2  # eixo da atividade é "y" (1); extras começam em "y2"
        eixo_id = f"y{indice_eixo}"
        fatia = serie.loc[dia]

        fig.add_trace(go.Scatter(
            x=fatia.index, y=fatia.values, mode="lines",
            name=rotulo, line=dict(color=cor, dash="dot"), yaxis=eixo_id,
        ))

        eixo = dict(
            title=dict(text=rotulo, font=dict(color=cor)),
            tickfont=dict(color=cor),
            range=faixa,
            overlaying="y",
            side="right",
        )
        if i > 0:
            # primeiro extra fica na borda direita da área do gráfico;
            # os seguintes precisam de eixo "livre" e posição explícita
            eixo["anchor"] = "free"
            eixo["position"] = fim_dominio_x + _LARGURA_EIXO_EXTRA * i
        layout[f"yaxis{indice_eixo}"] = eixo

    fig.update_layout(**layout)
    _sombrear_periodo_noturno(fig, inicio)
    if serie_evento is not None:
        _sombrear_eventos(fig, serie_evento, dia)
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

    # luz e temperatura são opcionais — nem todo dispositivo Condor as registra,
    # e quando a coluna existe mas vem vazia, max()/min() retornam NaN, o que
    # quebraria a faixa do eixo y do gráfico — por isso a checagem de "tem
    # dados utilizáveis" precisa rodar antes de montar as opções de exibição
    def _coluna_numerica_utilizavel(nome_coluna: str) -> pd.Series | None:
        if nome_coluna not in df.columns:
            return None
        valores = pd.to_numeric(df[nome_coluna], errors="coerce")
        return valores if valores.notna().any() else None

    luz_bruta = _coluna_numerica_utilizavel("LIGHT")
    temp_bruta = _coluna_numerica_utilizavel("TEMPERATURE")
    tem_luz = luz_bruta is not None
    tem_temperatura = temp_bruta is not None

    with st.expander("Opções de exibição"):
        modo_atividade = st.radio("Modo de atividade", MODOS_ATIVIDADE, horizontal=True)

        st.caption("Sinais exibidos no gráfico")
        col_a, col_l, col_t = st.columns(3)
        mostrar_atividade = col_a.checkbox(f"Atividade ({modo_atividade})", value=True)
        mostrar_luz = col_l.checkbox(
            "Luz", value=tem_luz, disabled=not tem_luz,
            help=None if tem_luz else "Este arquivo não possui registros de luz utilizáveis (coluna LIGHT).",
        )
        mostrar_temperatura = col_t.checkbox(
            "Temperatura", value=tem_temperatura, disabled=not tem_temperatura,
            help=None if tem_temperatura else "Este arquivo não possui registros de temperatura utilizáveis (coluna TEMPERATURE).",
        )

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

    serie_luz = None
    if mostrar_luz and luz_bruta is not None:
        serie_luz = pd.Series(luz_bruta.to_numpy(), index=pd.DatetimeIndex(df["DATE/TIME"]), name="luz")

    serie_temp = None
    if mostrar_temperatura and temp_bruta is not None:
        serie_temp = pd.Series(temp_bruta.to_numpy(), index=pd.DatetimeIndex(df["DATE/TIME"]), name="temperatura")

    if not (mostrar_atividade or serie_luz is not None or serie_temp is not None):
        st.info("Selecione ao menos um sinal em **Opções de exibição** para gerar o gráfico.")
        return

    modo = st.radio("Exibir", ["Um dia específico", "Todos os dias"], horizontal=True)

    if modo == "Um dia específico":
        rotulos = {_rotulo_dia(i, dia): (i, dia) for i, dia in enumerate(dias, start=1)}
        numero_dia, dia = rotulos[st.selectbox("Dia", list(rotulos.keys()))]
        st.plotly_chart(
            _grafico_combinado_dia(
                dia, numero_dia, raw.data.loc[dia], escala_y, modo_atividade, cor_atividade=COR_LINHA,
                mostrar_atividade=mostrar_atividade, serie_luz=serie_luz, serie_temp=serie_temp, serie_evento=serie_evento,
            ),
            width="stretch",
        )

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
        # um gráfico combinado por dia — cada um com seus próprios eixos —
        # em vez de um único grid, que ficaria ilegível com 3 sinais sobrepostos
        for i, dia in enumerate(dias, start=1):
            st.plotly_chart(
                _grafico_combinado_dia(
                    dia, i, raw.data.loc[dia], escala_y, modo_atividade, cor_atividade=COR_LINHA,
                    mostrar_atividade=mostrar_atividade, serie_luz=serie_luz, serie_temp=serie_temp, serie_evento=serie_evento,
                ),
                width="stretch",
            )

        st.divider()
        _metricas_ritmo(raw, titulo="Ritmo de repouso-atividade — registro completo")
