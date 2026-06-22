"""Página principal de análise de actigrafia de um único arquivo.

Construída em torno do objeto `BaseRaw` do pyActigraphy. Permite recortar o início
e o fim do registro, escolher os sinais exibidos e suas faixas, filtrar os dias
mostrados, ajustar os parâmetros das métricas não paramétricas (IS, IV, L5, M10) e
exportar dados (`.txt`/`.csv`) e gráficos (`.png`) em um `.zip`, salvando uma cópia
em "Exportar relatório".
"""

from __future__ import annotations

import base64
import datetime as _dt
import io
import json
from typing import cast

import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components
from controller.arquivo_controller import ArquivoController
from controller.relatorio_controller import RelatorioController
from view.ui import (
    render_toast, set_toast, get_usuario_id, rotulo_genero, coluna_numerica_utilizavel,
    carregar_actigrafia_cached, construir_raw_cached, grafico_combinado_dia,
    COR_LINHA, MODOS_ATIVIDADE, DIAS_SEMANA,
)


_PERIODOS_DIA = {
    "Dia inteiro":      (0, 24),
    "Manhã (06h–12h)":  (6, 12),
    "Tarde (12h–18h)":  (12, 18),
    "Noite (18h–24h)":  (18, 24),
}

_DURACOES_DESCARTE_H = list(range(0, 13, 2))

_PERIODOS_FIXOS = [
    (1,  "1 dia",   "1D"),
    (3,  "3 dias",  "3D"),
    (7,  "7 dias",  "7D"),
    (14, "14 dias", "14D"),
    (30, "30 dias", "30D"),
]

_LARGURA_COLAGEM = 1600
_ALTURA_GRAFICO_COLAGEM = 340

_ERROS_METRICA_RITMO = (KeyError, ValueError, ZeroDivisionError)
_AVISO_DADOS_INSUFICIENTES = (
    "Não foi possível calcular esta métrica para o registro selecionado — "
    "o pyActigraphy exige pelo menos 24h de dados contínuos para estimar o ritmo de repouso-atividade."
)


# ── Cache de I/O ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _gerar_export_zip(
    arquivo_id: int, usuario_id: int, df: pd.DataFrame,
    incluir_dados: bool, extras: tuple[tuple[str, bytes], ...],
) -> tuple:
    """Monta o ZIP de exportação com dados e/ou arquivos extras (cacheado).

    Recebe `extras` como tupla de pares (em vez de dict) para ser hasheável pelo
    cache do Streamlit.

    Args:
        arquivo_id: Id do arquivo de origem.
        usuario_id: Id do usuário dono.
        df: DataFrame com os dados (já recortado) a exportar.
        incluir_dados: Se True, inclui os arquivos `.txt` e `.csv`.
        extras: Pares `(nome_no_zip, conteúdo)` adicionais (ex.: PNG da colagem).

    Returns:
        tuple: `(zip_bytes, nome_arquivo)`; ou `(None, None)` se o arquivo de
        origem não for encontrado.
    """
    return ArquivoController.exportar_dados(arquivo_id, usuario_id, df, incluir_dados, dict(extras))


# ── Cálculo cacheado de métricas (pesado) ─────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _computar_metricas_globais(
    df: pd.DataFrame, nome: str, coluna: str,
    freq: str, limiar: int,
) -> dict | None:
    """Calcula as métricas de ritmo globais (IS, IV, L5, M10) do registro.

    Args:
        df: DataFrame Condor já recortado.
        nome: Nome/identificador do registro.
        coluna: Coluna de atividade usada (ex.: ``"PIM"``).
        freq: Frequência de reamostragem para IS e IV (ex.: ``"1H"``).
        limiar: Limiar de binarização da atividade.

    Returns:
        dict | None: Mapa com as chaves ``is``, ``iv``, ``l5`` e ``m10``; None se
        os dados forem insuficientes para o cálculo.
    """
    raw = construir_raw_cached(nome, df, coluna)
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
    freq: str, limiar: int, periodo: str,
) -> pd.DataFrame | None:
    """Calcula as métricas de ritmo por período (ISp, IVp, L5p, M10p).

    Args:
        df: DataFrame Condor já recortado.
        nome: Nome/identificador do registro.
        coluna: Coluna de atividade usada (ex.: ``"PIM"``).
        freq: Frequência de reamostragem para ISp e IVp (ex.: ``"1H"``).
        limiar: Limiar de binarização da atividade.
        periodo: Tamanho da janela de cada período (ex.: ``"7D"``).

    Returns:
        pandas.DataFrame | None: Tabela com uma linha por período e as colunas
        ``IS``, ``IV``, ``L5`` e ``M10``; None se os dados forem insuficientes.
    """
    raw = construir_raw_cached(nome, df, coluna)
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


# ── Preparação dos dados para exportação ──────────────────────────────────────

def _preparar_df_exportacao(
    df: pd.DataFrame,
    dt_index: pd.DatetimeIndex,
    modos_disponiveis: list[str],
    modo_atividade: str,
    mostrar_atividade: bool,
    escala_atividade: tuple[float, float],
    mostrar_luz: bool,
    escala_luz: tuple[float, float] | None,
    mostrar_temperatura: bool,
    escala_temperatura: tuple[float, float] | None,
    dias_exibidos: list[str],
    hora_inicio: int,
    hora_fim: int,
    faixa_luz_filtro: tuple[float, float] | None = None,
) -> pd.DataFrame:
    """Prepara uma cópia do DataFrame refletindo os recortes de exibição.

    Zera os valores de atividade, luz e temperatura que não correspondem aos
    sinais e filtros selecionados em "Opções de exibição" e "Filtrar dias
    exibidos", preservando todas as colunas e linhas (apenas o conteúdo dos
    sinais é zerado).

    Args:
        df: DataFrame Condor de origem (não é modificado).
        dt_index: Índice de timestamps pré-computado de `df`.
        modos_disponiveis: Modos de atividade presentes (ex.: ``["PIM", "TAT"]``).
        modo_atividade: Modo selecionado, único a ser preservado.
        mostrar_atividade: Se False, zera a atividade.
        escala_atividade: Faixa exibida da atividade; valores fora são zerados.
        mostrar_luz: Se False, zera a luz.
        escala_luz: Faixa exibida da luz, ou None.
        mostrar_temperatura: Se False, zera a temperatura.
        escala_temperatura: Faixa exibida da temperatura, ou None.
        dias_exibidos: Datas (``YYYY-MM-DD``) mantidas; demais linhas são zeradas.
        hora_inicio: Hora inicial (inclusive) do período exibido.
        hora_fim: Hora final (exclusive) do período exibido.
        faixa_luz_filtro: Faixa de luz; fora dela, atividade e temperatura são
            zeradas. None desativa esse filtro.

    Returns:
        pandas.DataFrame: Cópia com os sinais zerados conforme a seleção.
    """
    df = df.copy()

    def _zerar_fora_da_faixa(nome_coluna: str, faixa: tuple[float, float] | None) -> None:
        """Zera os valores de uma coluna fora da faixa `[min, max]` informada."""
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

    # filtro de luz: zera atividade e temperatura fora da faixa de Lux selecionada
    if faixa_luz_filtro is not None and "LIGHT" in df.columns:
        luz = pd.to_numeric(df["LIGHT"], errors="coerce")
        fora_da_luz = ~luz.between(*faixa_luz_filtro)
        colunas_atividade_temp = [c for c in (modo_atividade, "TEMPERATURE") if c in df.columns]
        if colunas_atividade_temp:
            df.loc[fora_da_luz.fillna(False).to_numpy(), colunas_atividade_temp] = 0

    return df


# ── Colagem dos gráficos diários ──────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _gerar_colagem_graficos(
    dias_exibidos: list[str],
    numero_por_dia: dict[str, int],
    raw_data: pd.Series,
    escala_atividade: tuple[float, float],
    rotulo_atividade: str,
    cor_atividade: str,
    mostrar_atividade: bool,
    serie_luz: pd.Series | None,
    serie_temp: pd.Series | None,
    serie_evento: pd.Series | None,
    escala_luz: tuple[float, float] | None,
    escala_temperatura: tuple[float, float] | None,
    hora_inicio: int,
    hora_fim: int,
    serie_luz_filtro: pd.Series | None = None,
    faixa_luz_filtro: tuple[float, float] | None = None,
) -> bytes:
    """Renderiza cada dia exibido como imagem e os empilha em uma colagem vertical.

    Gera o `grafico_combinado_dia` de cada dia, converte para PNG via kaleido e
    empilha as imagens (uma linha por dia, na ordem dos dias exibidos).

    Args:
        dias_exibidos: Datas (``YYYY-MM-DD``) a renderizar, na ordem desejada.
        numero_por_dia: Mapa data → número sequencial "Dia N" no registro.
        raw_data: Série de atividade do `BaseRaw`, indexada por timestamp.
        escala_atividade: Faixa `(min, max)` do eixo de atividade.
        rotulo_atividade: Rótulo do modo de atividade (ex.: ``"PIM"``).
        cor_atividade: Cor da linha de atividade.
        mostrar_atividade: Se False, omite a linha de atividade.
        serie_luz: Série de luz a sobrepor, ou None.
        serie_temp: Série de temperatura a sobrepor, ou None.
        serie_evento: Série de marcações de evento, ou None.
        escala_luz: Faixa do eixo de luz, ou None.
        escala_temperatura: Faixa do eixo de temperatura, ou None.
        hora_inicio: Hora inicial do recorte exibido.
        hora_fim: Hora final do recorte exibido.
        serie_luz_filtro: Série de luz usada para filtrar por faixa, ou None.
        faixa_luz_filtro: Faixa de luz para filtrar atividade/temperatura, ou None.

    Returns:
        bytes: Imagem PNG única com todos os gráficos diários empilhados.
    """
    imagens = []
    for dia in dias_exibidos:
        fig = grafico_combinado_dia(
            dia, numero_por_dia[dia], raw_data.loc[dia],
            escala_atividade, rotulo_atividade, cor_atividade=cor_atividade,
            mostrar_atividade=mostrar_atividade,
            serie_luz=serie_luz, serie_temp=serie_temp, serie_evento=serie_evento,
            escala_luz=escala_luz, escala_temperatura=escala_temperatura,
            hora_inicio=hora_inicio, hora_fim=hora_fim,
            serie_luz_filtro=serie_luz_filtro, faixa_luz_filtro=faixa_luz_filtro,
        )
        # Round-trip pelo JSON do plotly: serializa Timestamps/numpy antes do
        # kaleido, que não os aceita diretamente em add_vrect (x0/x1) e nos eixos.
        fig_serializavel = go.Figure(json.loads(pio.to_json(fig)))
        png = fig_serializavel.to_image(format="png", width=_LARGURA_COLAGEM, height=_ALTURA_GRAFICO_COLAGEM, scale=2)
        imagens.append(Image.open(io.BytesIO(png)))

    largura = max(im.width for im in imagens)
    altura_total = sum(im.height for im in imagens)
    colagem = Image.new("RGB", (largura, altura_total), "white")
    y = 0
    for im in imagens:
        colagem.paste(im, (0, y))
        y += im.height

    buf = io.BytesIO()
    colagem.save(buf, format="PNG")
    return buf.getvalue()


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
) -> None:
    """Exibe as métricas de ritmo do registro (globais ou por período).

    Mostra um aviso quando os dados são insuficientes para o cálculo.

    Args:
        df: DataFrame Condor já recortado.
        nome: Nome/identificador do registro.
        coluna: Coluna de atividade usada.
        titulo: Título da seção exibida.
        freq: Frequência de reamostragem para IS e IV.
        limiar: Limiar de binarização da atividade.
        usar_periodo: Se True, calcula por período (ISp/IVp/L5p/M10p) e exibe uma
            tabela; senão, exibe as métricas globais em cartões.
        periodo: Tamanho da janela de cada período (usado quando `usar_periodo`).
    """
    st.subheader(titulo)
    if usar_periodo:
        resultado = _computar_metricas_periodo(df, nome, coluna, freq, limiar, periodo)
        if resultado is None:
            st.info(_AVISO_DADOS_INSUFICIENTES)
        else:
            st.dataframe(resultado.style.format("{:.3f}"), width="stretch")
    else:
        resultado = _computar_metricas_globais(df, nome, coluna, freq, limiar)
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
    """Salva o ZIP exportado em "Exportar relatório" e agenda o toast de confirmação.

    Args:
        usuario_id: Id do usuário dono.
        nome_origem: Nome do arquivo `.txt` que originou a exportação.
        zip_nome: Nome do `.zip` exportado.
        zip_bytes: Conteúdo binário do `.zip`.
    """
    RelatorioController.salvar(usuario_id, zip_nome, nome_origem, zip_bytes)
    set_toast("Relatório exportado e salvo em Exportar relatório.")


# ── Página principal ──────────────────────────────────────────────────────────

def analises_page():
    """Renderiza a página de análises de actigrafia.

    Aplica o guard de autenticação, deixa escolher um arquivo, exibe os dados do
    sujeito e oferece os controles de recorte do registro, opções de exibição,
    filtros de dias e parâmetros das métricas. Mostra as métricas de ritmo e um
    gráfico combinado por dia exibido, além do fluxo de exportação com download
    automático do `.zip`.
    """
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

    opcoes_arquivo = {arq["nome"]: arq for arq in arquivos}
    nome_escolhido = st.selectbox("Arquivo", list(opcoes_arquivo.keys()))
    arquivo_id = opcoes_arquivo[nome_escolhido]["id"]

    metadata, df = carregar_actigrafia_cached(arquivo_id, usuario_id)
    if df.empty:
        st.warning("Não foi possível processar este arquivo.")
        return

    nome_sujeito = metadata.get("SUBJECT_NAME")
    col_nome, col_sexo, col_nascimento = st.columns(3)
    col_nome.caption(f"**Paciente:** {nome_sujeito.strip().upper() if nome_sujeito else '—'}")
    col_sexo.caption(f"**Sexo:** {rotulo_genero(metadata.get('SUBJECT_GENDER'))}")
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
                _DURACOES_DESCARTE_H, default=2, format_func=lambda h: f"{h}h",
                help="Remove os dados anteriores a esse intervalo, contado a partir do primeiro registro.",
            )
            if duracao_ini_h is None:
                duracao_ini_h = 2
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

    luz_bruta  = coluna_numerica_utilizavel(df, "LIGHT")
    temp_bruta = coluna_numerica_utilizavel(df, "TEMPERATURE")
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

    # raw usado apenas para raw.data.loc[dia] nos gráficos
    raw = construir_raw_cached(nome_escolhido, df, modo_atividade)

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
                "Dia da semana", DIAS_SEMANA, selection_mode="multi", default=DIAS_SEMANA,
                label_visibility="collapsed",
                help="Mostra apenas os gráficos dos dias que caem nos dias da semana selecionados.",
            ) or []

        with col_periodo:
            st.caption("Período do dia")
            rotulo_periodo = st.segmented_control(
                "Período do dia", [*_PERIODOS_DIA.keys(), "Personalizado"],
                default="Dia inteiro", label_visibility="collapsed",
                help="Recorta a janela de horário exibida em cada gráfico diário.",
            )
            if rotulo_periodo is None:
                rotulo_periodo = "Dia inteiro"
            if rotulo_periodo == "Personalizado":
                hora_inicio, hora_fim = st.slider(
                    "Intervalo de horário personalizado", min_value=0, max_value=24, value=(0, 24),
                    step=1, format="%dh", label_visibility="collapsed",
                )
            else:
                hora_inicio, hora_fim = _PERIODOS_DIA[rotulo_periodo]

        st.divider()
        st.caption("Faixa de luz (Lux)")
        filtrar_por_luz = st.checkbox(
            "Mostrar atividade e temperatura apenas quando a luz estiver na faixa selecionada",
            value=False, disabled=not tem_luz,
            help=None if tem_luz else "Este arquivo não possui registros de luz utilizáveis (coluna LIGHT).",
        )
        faixa_luz_filtro = None
        if filtrar_por_luz and faixa_total_luz is not None and faixa_total_luz[0] < faixa_total_luz[1]:
            faixa_luz_filtro = st.slider(
                "Faixa de Lux", min_value=faixa_total_luz[0], max_value=faixa_total_luz[1], value=faixa_total_luz,
                help="Oculta, nos gráficos de atividade e temperatura, os pontos cujo valor de luz esteja fora dessa faixa.",
            )

    dias_exibidos = [
        dia for dia in dias
        if DIAS_SEMANA[pd.Timestamp(dia).weekday()] in dias_semana_escolhidos
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

    serie_luz_filtro = None
    if faixa_luz_filtro is not None and luz_bruta is not None:
        serie_luz_filtro = pd.Series(luz_bruta.to_numpy(), index=dt_index, name="luz_filtro")

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
    )
    st.divider()

    if not dias_exibidos:
        st.info("Nenhum dia do registro corresponde aos filtros selecionados em **Filtrar dias exibidos**.")
    else:
        for dia in dias_exibidos:
            st.plotly_chart(
                grafico_combinado_dia(
                    dia, numero_por_dia[dia], raw.data.loc[dia],
                    escala_atividade, modo_atividade, cor_atividade=COR_LINHA,
                    mostrar_atividade=mostrar_atividade,
                    serie_luz=serie_luz, serie_temp=serie_temp, serie_evento=serie_evento,
                    escala_luz=escala_luz, escala_temperatura=escala_temperatura,
                    hora_inicio=hora_inicio, hora_fim=hora_fim,
                    serie_luz_filtro=serie_luz_filtro, faixa_luz_filtro=faixa_luz_filtro,
                ),
            )

    # ── Exportação ─────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Exportar")
    st.caption(
        "Selecione o que deseja incluir no .zip exportado. **Dados**: .txt no formato "
        "original (mesmas linhas de cabeçalho e campos) e .csv apenas com os campos e "
        "seus valores, após os recortes aplicados acima — sinais não selecionados em "
        "**Opções de exibição**, valores fora das faixas exibidas, linhas fora de "
        "**Filtrar dias exibidos** e, se ativado, pontos fora da **faixa de luz** "
        "selecionada são exportados zerados. **Gráficos**: imagem única "
        "com os gráficos diários exibidos acima, empilhados verticalmente — cada linha "
        "corresponde a um dia do registro."
    )

    # Dispara o download automaticamente após a exportação ser gerada
    export_pronto = st.session_state.pop("_export_pronto", None)
    if export_pronto and export_pronto[0] == arquivo_id:
        _, zip_bytes_pronto, zip_nome_pronto = export_pronto
        b64 = base64.b64encode(zip_bytes_pronto).decode()
        components.html(
            f"""<script>
            (function() {{
                var a = window.parent.document.createElement('a');
                a.href = 'data:application/zip;base64,{b64}';
                a.download = '{zip_nome_pronto}';
                window.parent.document.body.appendChild(a);
                a.click();
                window.parent.document.body.removeChild(a);
            }})();
            </script>""",
            height=0,
        )

    col_chk_dados, col_chk_graficos = st.columns(2)
    incluir_dados = col_chk_dados.checkbox("Dados (.txt + .csv)", value=True)
    incluir_graficos = col_chk_graficos.checkbox(
        "Gráficos (.png)", value=True, disabled=not dias_exibidos,
        help=None if dias_exibidos else "Nenhum dia exibido — ajuste os filtros em **Filtrar dias exibidos**.",
    )
    st.caption("Uma cópia também é salva em **Exportar relatório**.")

    if not incluir_dados and not incluir_graficos:
        st.info("Selecione ao menos uma opção para gerar a exportação.")
    elif st.button("Baixar exportação (.zip)", type="primary"):
        with st.spinner("Gerando exportação..."):
            nome_base = nome_escolhido.rsplit(".", 1)[0]
            extras: dict[str, bytes] = {}
            if incluir_graficos and dias_exibidos:
                colagem_bytes = _gerar_colagem_graficos(
                    dias_exibidos, numero_por_dia, raw.data,
                    escala_atividade, modo_atividade, COR_LINHA, mostrar_atividade,
                    serie_luz, serie_temp, serie_evento, escala_luz, escala_temperatura,
                    hora_inicio, hora_fim,
                    serie_luz_filtro=serie_luz_filtro, faixa_luz_filtro=faixa_luz_filtro,
                )
                extras[f"{nome_base}_graficos.png"] = colagem_bytes

            df_exportar = _preparar_df_exportacao(
                df, dt_index, modos_disponiveis, modo_atividade,
                mostrar_atividade, escala_atividade,
                mostrar_luz, escala_luz, mostrar_temperatura, escala_temperatura,
                dias_exibidos, hora_inicio, hora_fim,
                faixa_luz_filtro=faixa_luz_filtro,
            )
            zip_bytes, zip_nome = _gerar_export_zip(
                arquivo_id, usuario_id, df_exportar, incluir_dados, tuple(extras.items()),
            )

        if zip_bytes:
            _salvar_relatorio(usuario_id, nome_escolhido, zip_nome, zip_bytes)
            st.session_state["_export_pronto"] = (arquivo_id, zip_bytes, zip_nome)
            st.rerun()
        else:
            st.warning("Não foi possível gerar a exportação.")
