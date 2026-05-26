import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from model.condor_parser import carregar_condor, dias_disponiveis, filtrar_dia
import glob


def analises_page():
    # ─────────────────────────────────────────────
    # 1. CONFIGURAÇÃO DA PÁGINA
    # ─────────────────────────────────────────────
    st.title("Análises")
    st.divider()
    # ══════════════════════════════════════════════════════════════
    # SELEÇÃO DO ARQUIVO — na própria página
    # ══════════════════════════════════════════════════════════════

    # Busca todos os .txt dentro de dados/
    arquivos = sorted(glob.glob("view/pages/dados/*.txt"))

    if not arquivos:
        st.warning("Nenhum arquivo encontrado em `dados/`. Coloque os .txt nessa pasta.")
        st.stop()

    # Monta um dicionário {nome_exibido: caminho_completo}
    opcoes = {a.split("/")[-1].replace(".txt", ""): a for a in arquivos}

    col_arq, col_dia = st.columns(2)

    with col_arq:
        nome_escolhido = st.selectbox("Arquivo", list(opcoes.keys()))

    caminho = opcoes[nome_escolhido]

    # ── carrega e faz cache do arquivo ──────────────────────────────
    @st.cache_data
    def carregar(path: str):
        return carregar_condor(path)

    metadata, df_total = carregar(caminho)

    # ── seleção do dia ───────────────────────────────────────────────
    dias = dias_disponiveis(df_total)

    with col_dia:
        dia = st.selectbox(
            "Dia",
            dias,
            format_func=lambda d: d,  # formato YYYY-MM-DD, troque se preferir
        )

    df = filtrar_dia(df_total, dia)

    if df.empty:
        st.warning("Sem dados para esse dia.")
        st.stop()

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # MÉTRICAS RÁPIDAS
    # ══════════════════════════════════════════════════════════════
    m1, m2, m3 = st.columns(3)
    m1.metric("PIM total", f"{df['pim'].sum():,.0f}")
    m2.metric("Pico PIM", f"{df['pim'].max():,.0f}")
    m3.metric("Temp. média", f"{df['temperatura'].mean():.1f} °C")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # GRÁFICOS
    # ══════════════════════════════════════════════════════════════

    # ── PIM ao longo do dia ─────────────────────────────────────────
    st.subheader("Atividade (PIM)")

    fig_pim = go.Figure()
    fig_pim.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["pim"],
        mode="lines",
        name="PIM",
        line=dict(color="#234cbe", width=1.5),
        fill="tozeroy",
        fillcolor="rgba(29,78,216,0.1)",
    ))
    fig_pim.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(tickformat="%H:%M"),
        yaxis_title="PIM",
        hovermode="x unified",
    )
    st.plotly_chart(fig_pim, use_container_width=True)

    # ── Temperatura e Luz lado a lado ───────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Temperatura (°C)")
        fig_temp = px.line(df, x="timestamp", y="temperatura", color_discrete_sequence=["#c43903"])
        fig_temp.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0),
                               xaxis=dict(tickformat="%H:%M"), xaxis_title="", yaxis_title="°C")
        st.plotly_chart(fig_temp, use_container_width=True)

    with c2:
        st.subheader("Luz (Lux)")
        # agrega por hora para o gráfico ficar legível
        df_hora = (df.set_index("timestamp")["luz"]
                   .resample("1h").mean()
                   .reset_index().rename(columns={"timestamp": "hora"}))
        fig_luz = px.bar(df_hora, x="hora", y="luz", color_discrete_sequence=["#ffb433"])
        fig_luz.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0),
                              xaxis=dict(tickformat="%H:%M"), xaxis_title="", yaxis_title="Lux")
        st.plotly_chart(fig_luz, use_container_width=True)

    # ── Melanopic EDI (se tiver dados) ──────────────────────────────
    if "melanopic" in df.columns and df["melanopic"].sum() > 0:
        st.subheader("Melanopic EDI")
        fig_mel = px.line(df, x="timestamp", y="melanopic", color_discrete_sequence=["#7c3aed"])
        fig_mel.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0),
                              xaxis=dict(tickformat="%H:%M"), xaxis_title="", yaxis_title="EDI")
        st.plotly_chart(fig_mel, use_container_width=True)

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # METADADOS DO DISPOSITIVO
    # ══════════════════════════════════════════════════════════════
    with st.expander("Metadados do arquivo"):
        st.json(metadata)