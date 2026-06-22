"""Página de análise de temperatura de um único arquivo.

Para os sinais de temperatura disponíveis (`TEMPERATURE` e/ou `EXT TEMPERATURE`),
monta uma matriz dia × hora com a média horária, um gráfico de médias por hora,
a matriz estilizada por escala de cores e estatísticas descritivas. Permite
exportar tabelas (`.csv`) e o gráfico (`.png`) em um `.zip`, salvando uma cópia
em "Exportar relatório".
"""

from __future__ import annotations

import base64

import pandas as pd
import plotly.graph_objs as go
import streamlit as st
import streamlit.components.v1 as components
from controller.arquivo_controller import ArquivoController
from controller.relatorio_controller import RelatorioController
from view.ui import (
    render_toast, set_toast, get_usuario_id, rotulo_genero, calcular_idade, coluna_numerica_utilizavel,
    carregar_actigrafia_cached,
)


COR_TEMPERATURA     = "#c43903"
COR_TEMPERATURA_EXT = "#1f77b4"


# ── Cache de I/O ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _gerar_export_zip(arquivo_id: int, usuario_id: int, extras: tuple[tuple[str, bytes], ...]) -> tuple:
    """Monta o ZIP de exportação apenas com arquivos extras (cacheado).

    Recebe `extras` como tupla de pares (em vez de dict) para ser hasheável pelo
    cache do Streamlit.

    Args:
        arquivo_id: Id do arquivo de origem.
        usuario_id: Id do usuário dono.
        extras: Pares `(nome_no_zip, conteúdo)` a incluir (CSVs e/ou PNG).

    Returns:
        tuple: `(zip_bytes, nome_arquivo)`; ou `(None, None)` se o arquivo de
        origem não for encontrado.
    """
    return ArquivoController.exportar_dados(arquivo_id, usuario_id, pd.DataFrame(), incluir_dados=False, extras=dict(extras))


# ── Matriz dia × hora ─────────────────────────────────────────────────────────

_DIAS_SEMANA_ABREV = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _matriz_temperatura_horaria(df: pd.DataFrame, temperatura: pd.Series) -> pd.DataFrame:
    """Monta a matriz dia × hora com a temperatura média de cada hora.

    Cada célula é a média da temperatura naquela hora (00h–23h) daquele dia.
    Acrescenta uma coluna "Média" (média das horas do dia) e uma linha "Média"
    (média de cada hora entre todos os dias). O índice combina data e o dia da
    semana abreviado.

    Args:
        df: DataFrame Condor com a coluna `DATE/TIME`.
        temperatura: Série de temperatura alinhada às linhas de `df`.

    Returns:
        pandas.DataFrame: Matriz com 24 colunas horárias mais a coluna/linha
        "Média".
    """
    dt = pd.DatetimeIndex(df["DATE/TIME"])
    base = pd.DataFrame({
        "dia": dt.strftime("%Y-%m-%d"),
        "hora": dt.hour,
        "temperatura": temperatura.to_numpy(),
    })
    matriz = base.pivot_table(index="dia", columns="hora", values="temperatura", aggfunc="mean")
    matriz = matriz.reindex(columns=range(24))
    matriz.columns = [f"{h:02d}h" for h in range(24)]
    datas = pd.to_datetime(matriz.index)
    matriz.index = [
        f"{data.strftime('%d/%m/%Y')} ({_DIAS_SEMANA_ABREV[data.weekday()]})" for data in datas
    ]
    matriz.index.name = "Dia"
    matriz["Média"] = matriz.mean(axis=1)
    matriz.loc["Média"] = matriz.mean(axis=0)
    return matriz


def _grafico_medias_horarias(matriz: pd.DataFrame | None, matriz_ext: pd.DataFrame | None) -> go.Figure:
    """Monta o gráfico de linha da temperatura média por hora (00h–23h).

    Desenha uma linha por sinal disponível, lendo a linha "Média" de cada matriz.

    Args:
        matriz: Matriz da temperatura interna, ou None se ausente.
        matriz_ext: Matriz da temperatura externa, ou None se ausente.

    Returns:
        plotly.graph_objs.Figure: Figura com as médias horárias.
    """
    horas = [f"{h:02d}h" for h in range(24)]

    fig = go.Figure()
    if matriz is not None:
        fig.add_trace(go.Scatter(
            x=horas, y=matriz.loc["Média", horas],
            mode="lines+markers", name="Temperatura",
            line=dict(color=COR_TEMPERATURA),
        ))
    if matriz_ext is not None:
        fig.add_trace(go.Scatter(
            x=horas, y=matriz_ext.loc["Média", horas],
            mode="lines+markers", name="Temperatura externa",
            line=dict(color=COR_TEMPERATURA_EXT),
        ))

    fig.update_layout(
        title=dict(text="Temperatura média por hora", x=0.01, xanchor="left"),
        xaxis=dict(title="Hora do dia"),
        yaxis=dict(title="Temperatura (°C)"),
        height=350,
        margin=dict(l=0, r=0, t=60, b=0),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _faixa_valores(matriz: pd.DataFrame) -> tuple[float, float]:
    """Calcula a faixa de valores da matriz, ignorando a linha/coluna "Média".

    Args:
        matriz: Matriz dia × hora (com a linha e a coluna "Média" no fim).

    Returns:
        tuple[float, float]: Par `(mínimo, máximo)` dos valores horários.
    """
    dados = matriz.iloc[:-1, :-1]
    return float(dados.min().min()), float(dados.max().max())


def _legenda_escala_cores(vmin: float, vmax: float) -> None:
    """Renderiza a barra de gradiente da escala de cores (azul = frio, vermelho = quente).

    Args:
        vmin: Valor mínimo da faixa (extremidade fria).
        vmax: Valor máximo da faixa (extremidade quente).
    """
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin:2px 0 10px 0;">
            <span style="font-size:12px;color:#666;white-space:nowrap;">❄️ {vmin:.2f} °C</span>
            <div style="flex:1;height:10px;border-radius:5px;
                        background:linear-gradient(to right, rgba(0,110,255,0.35), rgba(255,110,0,0.35));"></div>
            <span style="font-size:12px;color:#666;white-space:nowrap;">{vmax:.2f} °C 🔥</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _estilizar_matriz(matriz: pd.DataFrame):
    """Aplica formatação e escala de cores à matriz de temperatura.

    Colore cada célula conforme a posição do valor na faixa do registro (azul =
    frio, vermelho = quente), destaca a linha/coluna "Média" e fixa cabeçalhos.

    Args:
        matriz: Matriz dia × hora a estilizar.

    Returns:
        pandas.io.formats.style.Styler: Objeto de estilo pronto para `to_html()`.
    """
    idx_media_linha = matriz.shape[0] - 1
    idx_media_coluna = matriz.shape[1] - 1

    # Faixa relativa ao próprio registro, excluindo a linha e a coluna "Média".
    vmin, vmax = _faixa_valores(matriz)

    def _cor_celula(valor: float) -> str:
        if pd.isna(valor) or vmax == vmin:
            return ""
        frac = (valor - vmin) / (vmax - vmin)
        r, b = round(255 * frac), round(255 * (1 - frac))
        return f"background-color: rgba({r}, 110, {b}, 0.35)"

    return (
        matriz.style
        .format("{:.2f}", na_rep="-")
        .map(_cor_celula)
        .set_table_styles([
            {"selector": "table", "props": [("table-layout", "fixed"), ("width", "100%"), ("border-collapse", "collapse"), ("font-size", "13px")]},
            {"selector": "th, td", "props": [("text-align", "center"), ("width", "64px"), ("padding", "5px"), ("border", "1px solid #e3e3e3")]},
            {"selector": "th.row_heading", "props": [("width", "130px"), ("text-align", "left"), ("padding-left", "10px")]},
            {"selector": "th", "props": [("background-color", "#cfe2f3"), ("color", "#1a3a5c"), ("font-weight", "600")]},
            {"selector": "thead th", "props": [("position", "sticky"), ("top", "0"), ("z-index", "2")]},
            {"selector": "tbody th", "props": [("position", "sticky"), ("left", "0"), ("z-index", "1")]},
            {"selector": "thead th.blank", "props": [("position", "sticky"), ("left", "0"), ("top", "0"), ("z-index", "3")]},
            {"selector": "tbody tr:hover td, tbody tr:hover th", "props": [("filter", "brightness(0.94)")]},
            {"selector": f"th.row_heading.level0.row{idx_media_linha}", "props": [("background-color", "#d9d9d9")]},
            {"selector": f"th.col_heading.level0.col{idx_media_coluna}", "props": [("background-color", "#d9d9d9")]},
        ])
        .set_properties(subset=pd.IndexSlice["Média", :], **{"background-color": "#ececec", "font-weight": "bold"})
        .set_properties(subset=pd.IndexSlice[:, "Média"], **{"background-color": "#ececec", "font-weight": "bold"})
    )


def _renderizar_matriz(matriz: pd.DataFrame) -> None:
    """Exibe a legenda de cores e a matriz estilizada em um contêiner rolável.

    Args:
        matriz: Matriz dia × hora a renderizar.
    """
    vmin, vmax = _faixa_valores(matriz)
    _legenda_escala_cores(vmin, vmax)
    html = _estilizar_matriz(matriz).to_html()
    st.markdown(
        f'<div style="overflow:auto;max-height:480px;border:1px solid #dcdcdc;border-radius:10px;">{html}</div>',
        unsafe_allow_html=True,
    )


# ── Estatísticas descritivas ──────────────────────────────────────────────────

_HELP_ESTATISTICAS = {
    "Amplitude": "Diferença entre o maior e o menor valor registrado.",
    "Desvio padrão": "Dispersão dos valores em torno da média.",
    "Variância": "Quadrado do desvio padrão — mede a dispersão dos valores.",
}


def _calcular_estatisticas(serie: pd.Series) -> dict[str, float]:
    """Calcula estatísticas descritivas (°C) sobre todos os registros da série.

    Args:
        serie: Série de temperatura.

    Returns:
        dict[str, float]: Média, mediana, mínimo, máximo, amplitude, desvio
        padrão e variância, indexados pelo respectivo rótulo.
    """
    minimo, maximo = float(serie.min()), float(serie.max())
    return {
        "Média": float(serie.mean()),
        "Mediana": float(serie.median()),
        "Mínimo": minimo,
        "Máximo": maximo,
        "Amplitude": maximo - minimo,
        "Desvio padrão": float(serie.std()),
        "Variância": float(serie.var()),
    }


def _exibir_estatisticas(serie: pd.Series) -> None:
    """Exibe as estatísticas descritivas em um cartão, uma métrica por coluna.

    Args:
        serie: Série de temperatura sobre a qual calcular as estatísticas.
    """
    with st.container(border=True):
        st.markdown("**📊 Estatísticas descritivas**")
        for col, (rotulo, valor) in zip(st.columns(7), _calcular_estatisticas(serie).items()):
            unidade = "°C²" if rotulo == "Variância" else "°C"
            col.metric(rotulo, f"{valor:.2f} {unidade}", help=_HELP_ESTATISTICAS.get(rotulo))


def _estatisticas_para_csv(serie: pd.Series) -> bytes:
    """Serializa as estatísticas descritivas de uma série em CSV.

    Args:
        serie: Série de temperatura.

    Returns:
        bytes: CSV com as colunas ``Estatística`` e ``Valor (°C)``, em UTF-8.
    """
    df_stats = pd.DataFrame(_calcular_estatisticas(serie).items(), columns=["Estatística", "Valor (°C)"])
    return df_stats.to_csv(index=False).encode("utf-8")


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

def analise_temperatura_page():
    """Renderiza a página de análise de temperatura.

    Aplica o guard de autenticação, deixa escolher um arquivo, exibe os dados do
    sujeito e, para cada sinal de temperatura utilizável, mostra o gráfico de
    médias horárias, a matriz dia × hora e as estatísticas. Trata também o fluxo
    de exportação e o download automático do `.zip`.
    """
    st.title("Análise de temperatura")
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
    col_nome, col_sexo, col_idade = st.columns(3)
    col_nome.caption(f"**Paciente:** {nome_sujeito.strip().upper() if nome_sujeito else '—'}")
    col_sexo.caption(f"**Sexo:** {rotulo_genero(metadata.get('SUBJECT_GENDER'))}")
    col_idade.caption(f"**Idade:** {calcular_idade(metadata.get('SUBJECT_DATE_OF_BIRTH'))}")

    temperatura = coluna_numerica_utilizavel(df, "TEMPERATURE")
    temperatura_ext = coluna_numerica_utilizavel(df, "EXT TEMPERATURE")
    if temperatura is None and temperatura_ext is None:
        st.divider()
        st.info("Este arquivo não possui registros de temperatura utilizáveis (colunas TEMPERATURE ou EXT TEMPERATURE).")
        return

    matriz = _matriz_temperatura_horaria(df, temperatura) if temperatura is not None else None
    matriz_ext = _matriz_temperatura_horaria(df, temperatura_ext) if temperatura_ext is not None else None

    st.divider()
    st.plotly_chart(_grafico_medias_horarias(matriz, matriz_ext))

    if matriz is not None:
        st.divider()
        st.subheader("Temperatura média por hora (°C)")
        st.caption("As cores indicam a posição relativa de cada valor na faixa de temperatura do registro — do mais frio (azul) ao mais quente (vermelho).")
        _renderizar_matriz(matriz)
        _exibir_estatisticas(temperatura)

    if matriz_ext is not None:
        st.divider()
        st.subheader("Temperatura externa média por hora (°C)")
        st.caption("As cores indicam a posição relativa de cada valor na faixa de temperatura do registro — do mais frio (azul) ao mais quente (vermelho).")
        _renderizar_matriz(matriz_ext)
        _exibir_estatisticas(temperatura_ext)

    # ── Exportação ─────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Exportar")
    st.caption(
        "Exporta em um .zip as matrizes de temperatura média por hora e as estatísticas "
        "descritivas exibidas acima em .csv, além de uma imagem (.png) do gráfico de médias horárias."
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

    col_chk_tabelas, col_chk_grafico = st.columns(2)
    incluir_tabelas = col_chk_tabelas.checkbox("Tabelas (.csv)", value=True)
    incluir_grafico = col_chk_grafico.checkbox("Gráfico (.png)", value=True)
    st.caption("Uma cópia também é salva em **Exportar relatório**.")

    if not incluir_tabelas and not incluir_grafico:
        st.info("Selecione ao menos uma opção para gerar a exportação.")
    elif st.button("Baixar exportação (.zip)", type="primary"):
        with st.spinner("Gerando exportação..."):
            nome_base = nome_escolhido.rsplit(".", 1)[0]
            extras: dict[str, bytes] = {}
            if incluir_tabelas:
                if matriz is not None:
                    extras[f"{nome_base}_temperatura.csv"] = matriz.to_csv().encode("utf-8")
                    extras[f"{nome_base}_temperatura_estatisticas.csv"] = _estatisticas_para_csv(temperatura)
                if matriz_ext is not None:
                    extras[f"{nome_base}_temperatura_externa.csv"] = matriz_ext.to_csv().encode("utf-8")
                    extras[f"{nome_base}_temperatura_externa_estatisticas.csv"] = _estatisticas_para_csv(temperatura_ext)
            if incluir_grafico:
                png = _grafico_medias_horarias(matriz, matriz_ext).to_image(format="png", width=1200, height=400, scale=2)
                extras[f"{nome_base}_grafico_medias_horarias.png"] = png

            zip_bytes, zip_nome = _gerar_export_zip(arquivo_id, usuario_id, tuple(extras.items()))

        if zip_bytes:
            _salvar_relatorio(usuario_id, nome_escolhido, zip_nome, zip_bytes)
            st.session_state["_export_pronto"] = (arquivo_id, zip_bytes, zip_nome)
            st.rerun()
        else:
            st.warning("Não foi possível gerar a exportação.")