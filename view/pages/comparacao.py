"""Página de comparação de registros entre múltiplos arquivos.

Sobrepõe, em um gráfico por dia comparado, as séries de atividade (mais luz e
temperatura como eixos extras) de vários arquivos, com uma cor por arquivo e
escala compartilhada. Os dias podem ser alinhados pelo número do dia no registro
("Dia N") ou pelo dia da semana, normalizando datas calendário diferentes a uma
data de referência comum.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objs as go
import streamlit as st
from controller.arquivo_controller import ArquivoController
from view.ui import (
    render_toast, get_usuario_id, rotulo_genero, coluna_numerica_utilizavel,
    carregar_actigrafia_cached, construir_raw_cached, sombrear_periodo_noturno,
    MODOS_ATIVIDADE, DIAS_SEMANA, COR_LUZ, COR_TEMPERATURA, COR_LEGENDA, LARGURA_EIXO_EXTRA,
)


_PALETA_CORES = ["#234cbe", "#c43903", "#1f9e4c", "#9c27b0", "#e67e22", "#00838f"]

_REFERENCIA = pd.Timestamp("2000-01-01")


# ── Eixo de tempo relativo (alinha "Dia N" de registros com datas diferentes) ──

def _eixo_relativo(serie: pd.Series) -> pd.Series:
    """Reindexa uma série diária sobre a data de referência comum.

    Preserva a hora de cada ponto, mas substitui a data pela de referência
    (`2000-01-01`), permitindo sobrepor visualmente dias de datas calendário
    diferentes no eixo de 00:00 a 24:00.

    Args:
        serie: Série de um único dia, indexada por timestamp.

    Returns:
        pandas.Series: Cópia com o índice deslocado para a data de referência.
    """
    nova = serie.copy()
    nova.index = _REFERENCIA + (serie.index - serie.index.normalize())
    return nova


# ── Gráfico sobreposto de um "Dia N" ───────────────────────────────────────────

def _grafico_comparacao_dia(
    titulo: str,
    registros: list[dict],
    escala_atividade: tuple[float, float],
    rotulo_atividade: str,
    mostrar_atividade: bool,
    escala_luz: tuple[float, float] | None = None,
    escala_temperatura: tuple[float, float] | None = None,
) -> go.Figure:
    """Monta o gráfico sobreposto de um grupo de dias (um por arquivo).

    Desenha uma linha de atividade por registro e, quando habilitadas, as séries
    de luz e temperatura como eixos y extras tracejados. Todas as séries são
    normalizadas para a data de referência, de modo a alinhá-las no mesmo eixo de
    horas.

    Args:
        titulo: Título do gráfico (ex.: ``"Dia 1"`` ou ``"Sábado"``).
        registros: Lista de dicionários por arquivo, com `nome`, `cor`, `dia` e
            as séries `serie_atividade`, `serie_luz` e `serie_temp`.
        escala_atividade: Par `(min, max)` do eixo de atividade.
        rotulo_atividade: Rótulo do modo de atividade (ex.: ``"PIM"``).
        mostrar_atividade: Se False, omite as linhas de atividade.
        escala_luz: Par `(min, max)` do eixo de luz, ou None para ocultá-lo.
        escala_temperatura: Par `(min, max)` do eixo de temperatura, ou None.

    Returns:
        plotly.graph_objs.Figure: Figura comparativa do grupo de dias.
    """
    extras = [
        (rotulo, cor, chave, faixa)
        for rotulo, cor, chave, faixa in (
            ("Luz (Lux)",        COR_LUZ,         "serie_luz",  escala_luz),
            ("Temperatura (°C)", COR_TEMPERATURA, "serie_temp", escala_temperatura),
        )
        if faixa is not None and any(reg.get(chave) is not None for reg in registros)
    ]

    fim_dominio_x = 1 - LARGURA_EIXO_EXTRA * len(extras)

    fig = go.Figure()
    if mostrar_atividade:
        for reg in registros:
            serie = _eixo_relativo(reg["serie_atividade"])
            data_fmt = pd.Timestamp(reg["dia"]).strftime("%d/%m/%Y")
            fig.add_trace(go.Scatter(
                x=serie.index, y=serie.values, mode="lines",
                name=f"{reg['nome']} — {rotulo_atividade} ({data_fmt})",
                line=dict(color=reg["cor"]),
            ))

    layout = dict(
        title=dict(text=titulo, x=0.01, xanchor="left", font=dict(size=14, color=COR_LEGENDA)),
        xaxis=dict(
            title="Hora", domain=[0, fim_dominio_x],
            range=[_REFERENCIA, _REFERENCIA + pd.Timedelta(hours=24) - pd.Timedelta(seconds=1)],
            tickformat="%H:%M", dtick=3600000, showgrid=True,
            gridcolor="rgba(0, 0, 0, 0.15)", griddash="dot",
        ),
        yaxis=dict(title=rotulo_atividade, range=escala_atividade),
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

    for i, (rotulo, cor, chave, faixa) in enumerate(extras):
        indice_eixo = i + 2
        eixo_id = f"y{indice_eixo}"
        for reg in registros:
            serie = reg.get(chave)
            if serie is None:
                continue
            serie_rel = _eixo_relativo(serie)
            fig.add_trace(go.Scatter(
                x=serie_rel.index, y=serie_rel.values, mode="lines",
                name=f"{reg['nome']} — {rotulo}",
                line=dict(color=reg["cor"], dash="dot"), yaxis=eixo_id,
            ))
        eixo: dict = dict(
            title=dict(text=rotulo, font=dict(color=cor)),
            tickfont=dict(color=cor),
            range=faixa, overlaying="y", side="right",
        )
        if i > 0:
            eixo["anchor"]   = "free"
            eixo["position"] = fim_dominio_x + LARGURA_EIXO_EXTRA * i
        layout[f"yaxis{indice_eixo}"] = eixo

    fig.update_layout(**layout)
    sombrear_periodo_noturno(fig, _REFERENCIA)
    return fig


# ── Página principal ──────────────────────────────────────────────────────────

def comparacao_page():
    """Renderiza a página de comparação entre arquivos.

    Aplica o guard de autenticação, deixa selecionar dois ou mais arquivos,
    carrega-os e exibe os dados dos sujeitos. Oferece as opções de exibição (modo
    de atividade comum, sinais e escalas compartilhadas) e o alinhamento de dias
    (por número do dia ou por dia da semana), desenhando um gráfico sobreposto por
    grupo de dias resultante.
    """
    st.title("Comparação")
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
    nomes_escolhidos = st.multiselect(
        "Arquivos para comparar", list(opcoes_arquivo.keys()),
        help="Selecione dois ou mais arquivos para comparar.",
    )
    if len(nomes_escolhidos) < 2:
        st.info("Selecione ao menos dois arquivos para comparar.")
        return

    registros: list[dict] = []
    for i, nome in enumerate(nomes_escolhidos):
        arquivo_id = opcoes_arquivo[nome]["id"]
        metadata, df = carregar_actigrafia_cached(arquivo_id, usuario_id)
        if df.empty:
            st.warning(f"Não foi possível processar '{nome}' — ignorado.")
            continue
        registros.append({
            "nome": nome, "metadata": metadata, "df": df,
            "cor": _PALETA_CORES[i % len(_PALETA_CORES)],
        })

    if len(registros) < 2:
        st.warning("É necessário ao menos dois arquivos válidos para comparar.")
        return

    for reg in registros:
        meta = reg["metadata"]
        nome_sujeito = meta.get("SUBJECT_NAME")
        st.markdown(
            f"<span style='color:{reg['cor']}'>●</span> **{reg['nome']}** — "
            f"Paciente: {nome_sujeito.strip().upper() if nome_sujeito else '—'} · "
            f"Sexo: {rotulo_genero(meta.get('SUBJECT_GENDER'))}",
            unsafe_allow_html=True,
        )

    modos_comuns = [m for m in MODOS_ATIVIDADE if all(m in reg["df"].columns for reg in registros)]
    if not modos_comuns:
        st.warning("Nenhum modo de atividade (PIM/TAT/ZCM) é comum a todos os arquivos selecionados.")
        return

    # ── Opções de exibição ────────────────────────────────────────────────────
    with st.expander("Opções de exibição", expanded=True):
        modo_atividade = st.radio(
            "Modo de atividade", modos_comuns, horizontal=True,
            help="Medida de atividade motora usada nos gráficos — apenas modos presentes em todos os arquivos selecionados.",
        )
        faixa_total_atividade = (0.0, max(float(reg["df"][modo_atividade].max()) for reg in registros))

        for reg in registros:
            reg["luz_bruta"] = coluna_numerica_utilizavel(reg["df"], "LIGHT")
            reg["temp_bruta"] = coluna_numerica_utilizavel(reg["df"], "TEMPERATURE")

        tem_luz = any(reg["luz_bruta"] is not None for reg in registros)
        tem_temperatura = any(reg["temp_bruta"] is not None for reg in registros)

        valores_luz_max = [float(reg["luz_bruta"].max()) for reg in registros if reg["luz_bruta"] is not None]
        faixa_total_luz = (0.0, max(valores_luz_max)) if valores_luz_max else None

        valores_temp = [
            v for reg in registros if reg["temp_bruta"] is not None
            for v in (float(reg["temp_bruta"].min()), float(reg["temp_bruta"].max()))
        ]
        faixa_total_temp = (min(valores_temp), max(valores_temp)) if valores_temp else None

        st.divider()
        st.caption("Sinais exibidos no gráfico — escala compartilhada entre os arquivos selecionados")
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
            help=None if tem_luz else "Nenhum arquivo selecionado possui registros de luz utilizáveis (coluna LIGHT).",
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
            help=None if tem_temperatura else "Nenhum arquivo selecionado possui registros de temperatura utilizáveis (coluna TEMPERATURE).",
        )
        escala_temperatura = faixa_total_temp
        if mostrar_temperatura and faixa_total_temp is not None and faixa_total_temp[0] < faixa_total_temp[1]:
            escala_temperatura = col_t.slider(
                "Faixa exibida (°C)",
                min_value=faixa_total_temp[0], max_value=faixa_total_temp[1], value=faixa_total_temp,
                help="Recorta o eixo da temperatura para a faixa de valores selecionada, sem alterar os dados originais.",
            )

    if not (mostrar_atividade or (mostrar_luz and tem_luz) or (mostrar_temperatura and tem_temperatura)):
        st.info("Selecione ao menos um sinal em **Opções de exibição** para gerar o gráfico.")
        return

    # ── Preparação por arquivo ────────────────────────────────────────────────
    for reg in registros:
        df = reg["df"]
        dt_index = pd.DatetimeIndex(df["DATE/TIME"])
        reg["raw"] = construir_raw_cached(reg["nome"], df, modo_atividade)
        reg["dias"] = ArquivoController.dias_disponiveis(df)
        reg["serie_luz"]  = pd.Series(reg["luz_bruta"].to_numpy(),  index=dt_index) if (mostrar_luz and reg["luz_bruta"] is not None) else None
        reg["serie_temp"] = pd.Series(reg["temp_bruta"].to_numpy(), index=dt_index) if (mostrar_temperatura and reg["temp_bruta"] is not None) else None

    # ── Janela de dias para comparação ───────────────────────────────────────
    st.divider()
    st.subheader("Dias para comparar")
    st.caption("Os registros começam em datas diferentes — escolha como alinhar os dias de cada arquivo na comparação.")

    modo_alinhamento = st.radio(
        "Alinhar por", ["Número do dia do registro", "Dia da semana"], horizontal=True,
        help=(
            "Número do dia: compara o Dia 1 de cada arquivo com o Dia 1 dos demais, "
            "o Dia 2 com o Dia 2, e assim por diante — independente da data calendário.\n\n"
            "Dia da semana: compara o mesmo dia da semana entre os arquivos — por exemplo, "
            "sábado de um arquivo com sábado de outro. Usa a primeira ocorrência de cada "
            "dia da semana selecionado em cada arquivo."
        ),
    )

    grupos_dia: list[tuple[str, dict[str, str]]] = []  # (título do gráfico, {nome_arquivo: dia})

    if modo_alinhamento == "Número do dia do registro":
        max_dias = max(len(reg["dias"]) for reg in registros)
        indices_escolhidos = st.pills(
            "Dias (Dia N de cada registro)", list(range(1, max_dias + 1)),
            selection_mode="multi", default=[1], format_func=lambda n: f"Dia {n}",
            help="Cada número representa a posição do dia dentro do próprio registro de cada arquivo — Dia 1 é o primeiro dia gravado, Dia 2 o segundo, e assim por diante, mesmo que as datas de calendário sejam diferentes entre os arquivos.",
        ) or []
        for numero_dia in sorted(indices_escolhidos):
            mapa_dias = {
                reg["nome"]: reg["dias"][numero_dia - 1]
                for reg in registros if numero_dia <= len(reg["dias"])
            }
            grupos_dia.append((f"Dia {numero_dia}", mapa_dias))
    else:
        dias_semana_escolhidos = st.pills(
            "Dia da semana", DIAS_SEMANA, selection_mode="multi", default=[],
            help="Para cada dia da semana selecionado, é usada a primeira ocorrência desse dia dentro do registro de cada arquivo — por exemplo, selecionar 'Sábado' compara o primeiro sábado de cada arquivo.",
        ) or []
        for indice_semana, nome_semana in enumerate(DIAS_SEMANA):
            if nome_semana not in dias_semana_escolhidos:
                continue
            mapa_dias = {}
            for reg in registros:
                primeira_ocorrencia = next(
                    (dia for dia in reg["dias"] if pd.Timestamp(dia).weekday() == indice_semana), None,
                )
                if primeira_ocorrencia is not None:
                    mapa_dias[reg["nome"]] = primeira_ocorrencia
            grupos_dia.append((nome_semana, mapa_dias))

    if not grupos_dia:
        st.info("Selecione ao menos um dia para comparar.")
        return

    for titulo, mapa_dias in grupos_dia:
        registros_dia = []
        for reg in registros:
            dia_str = mapa_dias.get(reg["nome"])
            if dia_str is None:
                continue
            registros_dia.append({
                "nome": reg["nome"], "cor": reg["cor"], "dia": dia_str,
                "serie_atividade": reg["raw"].data.loc[dia_str],
                "serie_luz":  reg["serie_luz"].loc[dia_str]  if reg["serie_luz"]  is not None else None,
                "serie_temp": reg["serie_temp"].loc[dia_str] if reg["serie_temp"] is not None else None,
            })

        if not registros_dia:
            st.info(f"Nenhum arquivo selecionado possui um dia correspondente a '{titulo}'.")
            continue

        st.plotly_chart(
            _grafico_comparacao_dia(
                titulo, registros_dia, escala_atividade, modo_atividade,
                mostrar_atividade,
                escala_luz=escala_luz if mostrar_luz else None,
                escala_temperatura=escala_temperatura if mostrar_temperatura else None,
            ),
            key=f"comp_{titulo}",
        )
