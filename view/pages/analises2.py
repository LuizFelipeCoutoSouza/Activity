
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

# faixas de hora (início, fim) usadas tanto para recortar a janela exibida
# quanto para definir o intervalo do controle "Personalizado"
_PERIODOS_DIA = {
    "Dia inteiro": (0, 24),
    "Manhã (06h–12h)": (6, 12),
    "Tarde (12h–18h)": (12, 18),
    "Noite (18h–24h)": (18, 24),
}

# opções (em horas) do seletor de duração mínima da máscara de inatividade
_DURACOES_MASCARA_H = list(range(0, 13, 2))

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


def _rotulo_genero(valor: str | None) -> str:
    if not valor:
        return "—"
    # o Condor grava o gênero como sigla ou palavra, em português ou inglês
    # (ex.: "M", "Male", "Masculino") — a inicial basta para normalizar
    inicial = valor.strip().upper()[:1]
    if inicial == "M":
        return "MASCULINO"
    if inicial == "F":
        return "FEMININO"
    return valor.strip().upper()


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
    escala_luz: tuple[float, float] | None = None,
    escala_temperatura: tuple[float, float] | None = None,
    hora_inicio: int = 0,
    hora_fim: int = 24,
) -> go.Figure:
    inicio_dia = pd.Timestamp(dia)
    # janela exibida — pode ser um recorte do dia (ex.: só a manhã); o
    # sombreamento noturno continua relativo ao dia inteiro (inicio_dia)
    inicio = inicio_dia + pd.Timedelta(hours=hora_inicio)
    fim = inicio_dia + pd.Timedelta(hours=hora_fim) - pd.Timedelta(seconds=1)

    serie_atividade = serie_atividade.loc[inicio:fim]

    # luz e temperatura entram como eixos Y extras à direita — cada um com sua
    # própria escala — em vez de subplots separados, para permitir comparar os
    # três sinais lado a lado no tempo
    extras = [
        (rotulo, cor, serie, faixa)
        for rotulo, cor, serie, faixa in (
            ("Luz (Lux)", COR_LUZ, serie_luz, escala_luz),
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
        fatia = serie.loc[inicio:fim]

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
    _sombrear_periodo_noturno(fig, inicio_dia)
    if serie_evento is not None:
        _sombrear_eventos(fig, serie_evento, dia)
    return fig


_ERROS_METRICA_RITMO = (KeyError, ValueError, ZeroDivisionError)
_AVISO_DADOS_INSUFICIENTES = (
    "Não foi possível calcular esta métrica para o registro selecionado — "
    "o pyActigraphy exige pelo menos 24h de dados contínuos para estimar o ritmo de repouso-atividade."
)


def _metricas_ritmo(raw: BaseRaw, titulo: str = "Ritmo de repouso-atividade") -> None:
    st.subheader(titulo)

    # IS/IV/L5/M10 dependem de uma janela de atividade média ao longo do
    # dia; com registros curtos ou cheios de lacunas, o pyActigraphy chega
    # a uma janela vazia/toda NaN e KeyError: NaT ao buscar seu mínimo/máximo.
    try:
        valor_is, valor_iv, valor_l5, valor_m10 = raw.IS(), raw.IV(), raw.L5(), raw.M10()
    except _ERROS_METRICA_RITMO:
        st.info(_AVISO_DADOS_INSUFICIENTES)
        return

    col_is, col_iv, col_l5, col_m10 = st.columns(4)
    col_is.metric("IS — geral", f"{valor_is:.3f}",
                  help="Estabilidade interdiária: o quanto o padrão de repouso-atividade se repete de um dia para o outro.")
    col_iv.metric("IV — geral", f"{valor_iv:.3f}",
                  help="Variabilidade intradiária: o quanto a atividade se fragmenta ao longo do dia.")
    col_l5.metric("L5 — geral", f"{valor_l5:.3f}",
                  help="Atividade média durante as 5 horas menos ativas do dia (média entre todos os dias do registro).")
    col_m10.metric("M10 — geral", f"{valor_m10:.3f}",
                   help="Atividade média durante as 10 horas mais ativas do dia (média entre todos os dias do registro).")


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

    metadata, df = _carregar_actigrafia(arquivo_id, usuario_id)
    if df.empty:
        st.warning("Não foi possível processar este arquivo.")
        return

    nome_sujeito = metadata.get("SUBJECT_NAME")

    col_nome, col_sexo, col_nascimento = st.columns(3)
    col_nome.caption(f"**Paciente:** {nome_sujeito.strip().upper() if nome_sujeito else '—'}")
    col_sexo.caption(f"**Sexo:** {_rotulo_genero(metadata.get('SUBJECT_GENDER'))}")
    col_nascimento.caption(f"**Data de nascimento:** {metadata.get('SUBJECT_DATE_OF_BIRTH', '—')}")

    tem_evento = "EVENT" in df.columns

    # nem todo arquivo Condor registra os três modos de atividade — oferecer
    # um modo cuja coluna não existe faz _construir_raw (df[coluna]) lançar
    # KeyError e quebrar a página inteira, inclusive o cálculo de IS/IV/L5/M10
    modos_disponiveis = [modo for modo in MODOS_ATIVIDADE if modo in df.columns]
    if not modos_disponiveis:
        st.warning("Este arquivo não possui nenhuma coluna de atividade reconhecida (PIM, TAT ou ZCM).")
        return

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

    faixa_total_luz = (0.0, float(luz_bruta.max())) if luz_bruta is not None else None
    faixa_total_temp = (float(temp_bruta.min()), float(temp_bruta.max())) if temp_bruta is not None else None

    with st.expander("Opções de exibição"):
        modo_atividade = st.radio(
            "Modo de atividade", modos_disponiveis, horizontal=True,
            help="Medida de atividade motora usada no gráfico e no cálculo do ritmo de repouso-atividade.",
        )
        # a faixa total depende do modo escolhido acima, então só pode ser
        # calculada aqui dentro — ao contrário de luz/temperatura, que não mudam
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
                min_value=faixa_total_atividade[0], max_value=faixa_total_atividade[1], value=faixa_total_atividade,
                help="Recorta o eixo da atividade para a faixa de valores selecionada, sem alterar os dados originais.",
            )

        mostrar_luz = col_l.checkbox(
            "Luz", value=tem_luz, disabled=not tem_luz,
            help=None if tem_luz else "Este arquivo não possui registros de luz utilizáveis (coluna LIGHT).",
        )
        # cada faixa de valores fica logo abaixo do checkbox do seu sinal —
        # agrupamento por proximidade — e só aparece quando há variação a recortar
        escala_luz = faixa_total_luz
        if mostrar_luz and faixa_total_luz is not None and faixa_total_luz[0] < faixa_total_luz[1]:
            escala_luz = col_l.slider(
                "Faixa exibida (Lux)", min_value=faixa_total_luz[0], max_value=faixa_total_luz[1], value=faixa_total_luz,
                help="Recorta o eixo da luz para a faixa de valores selecionada, sem alterar os dados originais.",
            )

        mostrar_temperatura = col_t.checkbox(
            "Temperatura", value=tem_temperatura, disabled=not tem_temperatura,
            help=None if tem_temperatura else "Este arquivo não possui registros de temperatura utilizáveis (coluna TEMPERATURE).",
        )
        escala_temperatura = faixa_total_temp
        if mostrar_temperatura and faixa_total_temp is not None and faixa_total_temp[0] < faixa_total_temp[1]:
            escala_temperatura = col_t.slider(
                "Faixa exibida (°C)", min_value=faixa_total_temp[0], max_value=faixa_total_temp[1], value=faixa_total_temp,
                help="Recorta o eixo da temperatura para a faixa de valores selecionada, sem alterar os dados originais.",
            )


        st.divider()
        mostrar_eventos = st.checkbox(
            "Destacar marcações de evento (botão)",
            disabled=not tem_evento,
            help=None if tem_evento else "Este arquivo não possui registros de marcação de evento (coluna EVENT).",
        )

    raw = _construir_raw(nome_escolhido, df, modo_atividade)
    if mascarar_inatividade and duracao_mascara_h is not None:
        raw.create_inactivity_mask(f"{duracao_mascara_h}h")
        raw.mask_inactivity = True
    dias = ArquivoController.dias_disponiveis(df)

    # numeração original ("Dia N") preservada mesmo com filtro aplicado —
    # senão "Dia 1" mudaria de data conforme a seleção de dias da semana
    numero_por_dia = {dia: numero for numero, dia in enumerate(dias, start=1)}

    with st.expander("Filtrar dias exibidos"):
        st.caption("Filtros apenas de exibição — recortam os gráficos abaixo sem alterar os dados nem as métricas do registro completo.")

        col_semana, col_periodo = st.columns(2, gap="large")

        with col_semana:
            st.caption("Dia da semana")
            # pills em vez de multiselect: com só 7 opções fixas, selecionar
            # clicando é mais rápido do que abrir um dropdown e marcar uma a uma
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

    _metricas_ritmo(raw, titulo="Ritmo de repouso-atividade — registro completo")
    st.divider()

    if not dias_exibidos:
        st.info("Nenhum dia do registro corresponde aos filtros selecionados em **Filtrar dias exibidos**.")
        return

    # um gráfico combinado por dia — cada um com seus próprios eixos —
    # em vez de um único grid, que ficaria ilegível com 3 sinais sobrepostos
    for dia in dias_exibidos:
        st.plotly_chart(
            _grafico_combinado_dia(
                dia, numero_por_dia[dia], raw.data.loc[dia], escala_atividade, modo_atividade, cor_atividade=COR_LINHA,
                mostrar_atividade=mostrar_atividade, serie_luz=serie_luz, serie_temp=serie_temp, serie_evento=serie_evento,
                escala_luz=escala_luz, escala_temperatura=escala_temperatura,
                hora_inicio=hora_inicio, hora_fim=hora_fim,
            ),
            width="stretch",
        )
